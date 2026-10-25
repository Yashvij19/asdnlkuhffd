"""
RFC 4180 Compliant Streaming CSV Export Engine for Day-Ahead Schedules (FR-API-4).
Generates streaming CSV data with CRLF line endings, standard headers,
proper quoting/escaping, and Content-Disposition headers for utility day-ahead desks.
"""

import csv
import io
from collections.abc import Generator
from datetime import UTC, date, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.analytics.selection import select_day_ahead_forecast

CSV_HEADERS = [
    "delivery_date",
    "settlement_period",
    "start_time_utc",
    "start_time_london",
    "decision_date",
    "cutoff_time_london",
    "selected_publish_time_utc",
    "lead_time_hours",
    "forecast_mw",
    "actual_mw",
    "error_mw",
    "abs_error_mw",
    "direction",
]


def get_export_filename(
    decision_from: date, decision_to: date, cutoff_str: str = "09:00"
) -> str:
    """Generate standardized RFC 4180 attachment filename."""
    cutoff_clean = cutoff_str.replace(":", "")
    d_from_str = decision_from.strftime("%Y%m%d")
    d_to_str = decision_to.strftime("%Y%m%d")
    return f"day_ahead_wind_forecast_{d_from_str}_{d_to_str}_cutoff_{cutoff_clean}.csv"


def stream_day_ahead_csv(
    session: Session,
    decision_from: date,
    decision_to: date,
    cutoff_str: str = "09:00",
    tz_name: str = "Europe/London",
) -> Generator[str, None, None]:
    """
    Yield RFC 4180 compliant CSV lines for all settlement periods in the decision window.
    Uses CRLF line terminators and constant O(1) streaming memory.
    """
    if decision_from > decision_to:
        raise ValueError(
            f"decision_from ({decision_from}) cannot be after decision_to ({decision_to})"
        )

    tz = ZoneInfo(tz_name)
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\r\n")

    # 1. Header row
    writer.writerow(CSV_HEADERS)
    yield buf.getvalue()
    buf.seek(0)
    buf.truncate(0)

    # 2. Iterate each decision day
    curr_d = decision_from
    while curr_d <= decision_to:
        res = select_day_ahead_forecast(
            session=session,
            decision_date=curr_d,
            cutoff_str=cutoff_str,
            tz_name=tz_name,
        )

        for pt in res.points:
            # Format times
            st_utc = pt.start_time
            if st_utc.tzinfo is None:
                st_utc = st_utc.replace(tzinfo=UTC)
            else:
                st_utc = st_utc.astimezone(UTC)

            st_london = st_utc.astimezone(tz)
            start_london_str = st_london.strftime("%Y-%m-%d %H:%M")
            start_utc_str = st_utc.strftime("%Y-%m-%dT%H:%M:%SZ")

            pub_utc_str = ""
            if pt.forecast_publish_time:
                pt_pub = pt.forecast_publish_time
                if pt_pub.tzinfo is None:
                    pt_pub = pt_pub.replace(tzinfo=UTC)
                else:
                    pt_pub = pt_pub.astimezone(UTC)
                pub_utc_str = pt_pub.strftime("%Y-%m-%dT%H:%M:%SZ")

            lead_str = f"{pt.horizon_hours:.1f}" if pt.horizon_hours is not None else ""
            fc_str = f"{pt.forecast_mw:.1f}" if pt.forecast_mw is not None else ""
            act_str = f"{pt.actual_mw:.1f}" if pt.actual_mw is not None else ""
            err_str = f"{pt.error_mw:.1f}" if pt.error_mw is not None else ""
            abs_err_str = (
                f"{abs(pt.error_mw):.1f}" if pt.error_mw is not None else ""
            )

            direction = ""
            if pt.error_mw is not None:
                if pt.error_mw < -0.05:
                    direction = "SHORTFALL"
                elif pt.error_mw > 0.05:
                    direction = "SURPLUS"
                else:
                    direction = "BALANCED"

            row = [
                res.delivery_date,
                pt.settlement_period,
                start_utc_str,
                start_london_str,
                res.decision_date,
                cutoff_str,
                pub_utc_str,
                lead_str,
                fc_str,
                act_str,
                err_str,
                abs_err_str,
                direction,
            ]
            writer.writerow(row)
            yield buf.getvalue()
            buf.seek(0)
            buf.truncate(0)

        curr_d += timedelta(days=1)
