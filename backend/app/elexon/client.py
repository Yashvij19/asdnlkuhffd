"""
Resilient HTTP client for Elexon BMRS Insights API.
Provides date chunking, retries with exponential backoff and jitter, and a circuit breaker.
"""

import time
from collections.abc import Generator
from datetime import UTC, date, datetime, timedelta
from typing import Any, cast

import httpx
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_random_exponential,
)

from app.config import get_settings
from app.elexon.constants import (
    ELEXON_USER_AGENT,
    ENDPOINT_FUELHH_STREAM,
    ENDPOINT_WINDFOR_STREAM,
    FUEL_TYPE_WIND,
    PARAM_FUELHH_DATE_FROM,
    PARAM_FUELHH_DATE_TO,
    PARAM_FUELHH_FUEL_TYPE,
    PARAM_WINDFOR_PUBLISH_FROM,
    PARAM_WINDFOR_PUBLISH_TO,
)
from app.logging import get_logger

logger = get_logger("app.elexon.client")


class CircuitBreakerOpenError(Exception):
    """Raised when the circuit breaker is open to prevent hammering upstream API."""

    pass


class CircuitBreaker:
    """
    In-memory state machine implementing the Circuit Breaker pattern.
    Transitions: CLOSED -> OPEN (on N failures) -> HALF_OPEN (after recovery timeout) -> CLOSED.
    """

    def __init__(self, failure_threshold: int = 5, recovery_timeout_s: float = 30.0) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout_s = recovery_timeout_s
        self.failure_count = 0
        self.state: str = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        self.opened_at: float | None = None

    def can_execute(self) -> bool:
        """Return True if a request can proceed through the circuit breaker."""
        now = time.monotonic()
        if self.state == "CLOSED":
            return True
        elif self.state == "OPEN":
            if self.opened_at and (now - self.opened_at) >= self.recovery_timeout_s:
                self.state = "HALF_OPEN"
                logger.info("circuit_breaker_half_open", state="HALF_OPEN")
                return True
            return False
        elif self.state == "HALF_OPEN":
            # Allow limited probe requests in half-open state
            return True
        return False

    def record_success(self) -> None:
        """Reset failure counts and close the breaker on successful response."""
        self.failure_count = 0
        if self.state != "CLOSED":
            logger.info("circuit_breaker_closed", previous_state=self.state)
            self.state = "CLOSED"
        self.opened_at = None

    def record_failure(self) -> None:
        """Increment failure counter and trip breaker if threshold exceeded."""
        self.failure_count += 1
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
            self.opened_at = time.monotonic()
            logger.warning(
                "circuit_breaker_opened",
                failures=self.failure_count,
                recovery_timeout_s=self.recovery_timeout_s,
            )


def is_transient_error(exc: BaseException) -> bool:
    """Return True if exception is a retryable transient network/server error."""
    if isinstance(exc, (httpx.TimeoutException, httpx.NetworkError, httpx.ConnectError)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        # 429 Too Many Requests or 5xx Server Errors
        return exc.response.status_code == 429 or exc.response.status_code >= 500
    return False


def chunk_date_range(start_date: date, end_date: date, chunk_days: int) -> Generator[tuple[date, date], None, None]:
    """Yield sequential (chunk_start, chunk_end) inclusive date tuples respecting chunk_days."""
    current = start_date
    while current <= end_date:
        chunk_end = min(current + timedelta(days=chunk_days - 1), end_date)
        yield current, chunk_end
        current = chunk_end + timedelta(days=1)


def chunk_datetime_range(
    start_dt: datetime, end_dt: datetime, chunk_days: int
) -> Generator[tuple[datetime, datetime], None, None]:
    """Yield sequential (chunk_start, chunk_end) datetime tuples respecting chunk_days."""
    current = start_dt
    delta = timedelta(days=chunk_days)
    while current < end_dt:
        chunk_end = min(current + delta, end_dt)
        yield current, chunk_end
        current = chunk_end


class ElexonClient:
    """
    Resilient client for Elexon BMRS Insights API.
    Handles rate limits, exponential backoff, circuit breaking, and chunked fetching.
    """

    def __init__(
        self,
        base_url: str | None = None,
        timeout_s: float | None = None,
        max_retries: int | None = None,
        circuit_breaker: CircuitBreaker | None = None,
    ) -> None:
        settings = get_settings()
        self.base_url = (base_url or settings.elexon_base_url).rstrip("/")
        self.timeout_s = timeout_s or float(settings.http_timeout_s)
        self.max_retries = max_retries or settings.http_max_retries
        self.circuit_breaker = circuit_breaker or CircuitBreaker()
        self._headers = {
            "User-Agent": ELEXON_USER_AGENT,
            "Accept": "application/json",
        }

    def _execute_request(self, endpoint: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        """Execute HTTP GET with circuit breaker protection and tenacity retries."""
        if not self.circuit_breaker.can_execute():
            raise CircuitBreakerOpenError(
                "Circuit breaker is OPEN: Elexon BMRS API requests temporarily paused."
            )

        url = f"{self.base_url}{endpoint}"

        @retry(
            reraise=True,
            stop=stop_after_attempt(self.max_retries),
            wait=wait_random_exponential(multiplier=0.5, max=5.0),
            retry=retry_if_exception(is_transient_error),
        )
        def _call() -> list[dict[str, Any]]:
            with httpx.Client(timeout=self.timeout_s, headers=self._headers) as client:
                response = client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
                if isinstance(data, list):
                    return cast(list[dict[str, Any]], data)
                elif isinstance(data, dict) and "data" in data and isinstance(data["data"], list):
                    return cast(list[dict[str, Any]], data["data"])
                return []

        try:
            results = _call()
            self.circuit_breaker.record_success()
            return results
        except Exception as err:
            self.circuit_breaker.record_failure()
            logger.error("elexon_request_failed", endpoint=endpoint, error=str(err))
            raise

    def fetch_fuelhh_range(
        self, start_date: date, end_date: date, chunk_days: int = 3, inter_chunk_delay_s: float = 0.05
    ) -> list[dict[str, Any]]:
        """Fetch all FUELHH wind generation records for the specified settlement date range in polite chunks."""
        all_records: list[dict[str, Any]] = []

        for chunk_start, chunk_end in chunk_date_range(start_date, end_date, chunk_days):
            params = {
                PARAM_FUELHH_DATE_FROM: chunk_start.isoformat(),
                PARAM_FUELHH_DATE_TO: chunk_end.isoformat(),
                PARAM_FUELHH_FUEL_TYPE: FUEL_TYPE_WIND,
            }
            logger.info("fetching_fuelhh_chunk", date_from=chunk_start.isoformat(), date_to=chunk_end.isoformat())
            chunk_records = self._execute_request(ENDPOINT_FUELHH_STREAM, params)
            all_records.extend(chunk_records)
            if inter_chunk_delay_s > 0:
                time.sleep(inter_chunk_delay_s)

        return all_records

    def fetch_windfor_range(
        self, start_dt: datetime, end_dt: datetime, chunk_days: int = 3, inter_chunk_delay_s: float = 0.05
    ) -> list[dict[str, Any]]:
        """Fetch all WINDFOR forecast records published between start_dt and end_dt in polite chunks."""
        all_records: list[dict[str, Any]] = []

        # Ensure UTC timezone
        start_utc = start_dt.astimezone(UTC)
        end_utc = end_dt.astimezone(UTC)

        for chunk_start, chunk_end in chunk_datetime_range(start_utc, end_utc, chunk_days):
            params = {
                PARAM_WINDFOR_PUBLISH_FROM: chunk_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                PARAM_WINDFOR_PUBLISH_TO: chunk_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
            logger.info(
                "fetching_windfor_chunk",
                publish_from=params[PARAM_WINDFOR_PUBLISH_FROM],
                publish_to=params[PARAM_WINDFOR_PUBLISH_TO],
            )
            chunk_records = self._execute_request(ENDPOINT_WINDFOR_STREAM, params)
            all_records.extend(chunk_records)
            if inter_chunk_delay_s > 0:
                time.sleep(inter_chunk_delay_s)

        return all_records
