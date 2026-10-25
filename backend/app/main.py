"""
FastAPI Main Application.
Provides application lifecycle, middleware, and core endpoints.
"""

from collections.abc import AsyncGenerator, Generator
from contextlib import asynccontextmanager
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app import models as _models  # noqa: F401 - ensure models are registered on Base
from app.analytics.export import get_export_filename, stream_day_ahead_csv
from app.analytics.service import analytics_service
from app.config import get_settings
from app.db import Base, SessionLocal, engine, init_db
from app.ingest import seed_database_if_empty
from app.logging import get_logger, setup_logging
from app.middleware import register_middleware_and_handlers
from app.models import ActualWind, WindForecast
from app.schemas import (
    AccuracySummaryResult,
    BreakdownResult,
    CacheStats,
    DayAheadResult,
    DayAheadVintagesResult,
    DistributionResult,
    HorizonCurveResult,
    PersistenceBenchmarkResult,
    ProcurementBufferResult,
)

logger = get_logger("app.main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup and shutdown lifecycle management."""
    setup_logging()
    settings = get_settings()
    init_db()
    with SessionLocal() as session:
        seed_database_if_empty(session)
        # Pre-warm default analytics cache for sub-millisecond response
        try:
            warmed = analytics_service.warm_default_cache(session)
            logger.info("analytics_cache_warmed", entries=warmed.get("warmed_entries", 0))
        except Exception as exc:
            logger.warning("cache_warmup_failed", error=str(exc))
    logger.info("application_started", env=settings.app_env, version=settings.app_version)
    yield
    logger.info("application_shutdown")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance."""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="UK Day-Ahead Wind Generation Forecast Monitor API",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    # CORS Middleware
    origins = settings.cors_origins_list
    if not origins and settings.app_env.lower() == "development":
        origins = ["*"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins if origins else ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Production Middleware, Rate Limiting & RFC 7807 Handlers
    register_middleware_and_handlers(app)

    @app.get("/api/v1/health", tags=["System"])
    @app.get("/health", tags=["System"])
    async def health_check() -> dict[str, Any]:
        """Liveness health check endpoint."""
        return {
            "status": "healthy",
            "app": settings.app_name,
            "version": settings.app_version,
            "env": settings.app_env,
        }

    @app.get("/api/v1/ready", tags=["System"])
    @app.get("/ready", tags=["System"])
    async def readiness_check() -> dict[str, Any]:
        """
        Readiness probe verifying operational state, database connectivity,
        and seed snapshot completeness.
        """
        try:
            with SessionLocal() as session:
                session.execute(text("SELECT 1"))
                act_count = session.query(ActualWind).count()
                fc_count = session.query(WindForecast).count()

                if act_count == 0 or fc_count == 0:
                    raise HTTPException(
                        status_code=503,
                        detail=f"Database not fully ready: actual_wind={act_count}, wind_forecast={fc_count}",
                    )

                return {
                    "status": "ready",
                    "database": "connected",
                    "data_ready": True,
                    "row_counts": {
                        "actual_wind": act_count,
                        "wind_forecast": fc_count,
                    },
                    "decision_window": {
                        "start": settings.decision_month_start,
                        "end": settings.decision_month_end,
                    },
                }
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail=f"Database connectivity check failed: {exc}",
            ) from exc

    @app.get("/api/v1/meta", tags=["System"])
    async def get_metadata() -> dict[str, Any]:
        """Application metadata, configuration defaults, and attribution."""
        return {
            "app": settings.app_name,
            "version": settings.app_version,
            "env": settings.app_env,
            "decision_month_start": settings.decision_month_start,
            "decision_month_end": settings.decision_month_end,
            "default_cutoff": settings.default_cutoff,
            "timezone": settings.timezone,
            "elexon_base_url": settings.elexon_base_url,
            "chunk_days": settings.chunk_days,
            "attribution": settings.attribution,
        }

    @app.get("/api/v1/discovery/contracts", tags=["Discovery"])
    async def get_discovery_contracts() -> dict[str, Any]:
        """Return verified Elexon API endpoint definitions, parameter contracts, and sample data."""
        import json
        from pathlib import Path

        from app.elexon.constants import (
            ENDPOINT_FUELHH_STREAM,
            ENDPOINT_WINDFOR_STREAM,
            FUELHH_REQUIRED_FIELDS,
            PARAM_FUELHH_DATE_FROM,
            PARAM_FUELHH_DATE_TO,
            PARAM_FUELHH_FUEL_TYPE,
            PARAM_WINDFOR_PUBLISH_FROM,
            PARAM_WINDFOR_PUBLISH_TO,
            WINDFOR_REQUIRED_FIELDS,
        )

        fixtures_dir = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
        fuelhh_path = fixtures_dir / "elexon_fuelhh_sample.json"
        windfor_path = fixtures_dir / "elexon_windfor_sample.json"

        fuelhh_sample: list[dict[str, Any]] = []
        if fuelhh_path.exists():
            with open(fuelhh_path, encoding="utf-8") as f:
                fuelhh_sample = json.load(f)

        windfor_sample: list[dict[str, Any]] = []
        if windfor_path.exists():
            with open(windfor_path, encoding="utf-8") as f:
                windfor_sample = json.load(f)

        return {
            "status": "verified",
            "base_url": settings.elexon_base_url,
            "datasets": {
                "FUELHH": {
                    "endpoint": ENDPOINT_FUELHH_STREAM,
                    "parameters": {
                        "from": PARAM_FUELHH_DATE_FROM,
                        "to": PARAM_FUELHH_DATE_TO,
                        "fuel_type": PARAM_FUELHH_FUEL_TYPE,
                    },
                    "required_fields": list(FUELHH_REQUIRED_FIELDS),
                    "fixture_record_count": len(fuelhh_sample),
                    "sample": fuelhh_sample[0] if fuelhh_sample else None,
                },
                "WINDFOR": {
                    "endpoint": ENDPOINT_WINDFOR_STREAM,
                    "parameters": {
                        "from": PARAM_WINDFOR_PUBLISH_FROM,
                        "to": PARAM_WINDFOR_PUBLISH_TO,
                    },
                    "required_fields": list(WINDFOR_REQUIRED_FIELDS),
                    "fixture_record_count": len(windfor_sample),
                    "sample": windfor_sample[0] if windfor_sample else None,
                },
            },
        }

    @app.get("/api/v1/storage/status", tags=["Storage"])
    async def get_storage_status() -> dict[str, Any]:
        """Return database connection status, initialized tables, and parser verification results."""
        import json
        from pathlib import Path

        from app.elexon.parsers import parse_fuelhh_batch, parse_windfor_batch

        fixtures_dir = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
        fuelhh_path = fixtures_dir / "elexon_fuelhh_sample.json"
        windfor_path = fixtures_dir / "elexon_windfor_sample.json"

        fuelhh_valid = 0
        fuelhh_rejected = 0
        if fuelhh_path.exists():
            with open(fuelhh_path, encoding="utf-8") as f:
                fuelhh_res = parse_fuelhh_batch(json.load(f))
                fuelhh_valid = len(fuelhh_res.valid_rows)
                fuelhh_rejected = fuelhh_res.rejected_count

        windfor_valid = 0
        windfor_rejected = 0
        if windfor_path.exists():
            with open(windfor_path, encoding="utf-8") as f:
                windfor_res = parse_windfor_batch(json.load(f))
                windfor_valid = len(windfor_res.valid_rows)
                windfor_rejected = windfor_res.rejected_count

        from sqlalchemy import func, select

        from app.models import ActualWind, IngestRun, WindForecast

        actual_count = 0
        forecast_count = 0
        recent_runs: list[dict[str, Any]] = []

        with SessionLocal() as session:
            actual_count = session.scalar(select(func.count()).select_from(ActualWind)) or 0
            forecast_count = session.scalar(select(func.count()).select_from(WindForecast)) or 0
            runs = session.scalars(
                select(IngestRun).order_by(IngestRun.id.desc()).limit(5)
            ).all()
            recent_runs = [
                {
                    "id": r.id,
                    "dataset": r.dataset,
                    "status": r.status,
                    "range": f"{r.range_from} to {r.range_to}",
                    "upserted": r.rows_upserted,
                    "rejected": r.rows_rejected,
                    "started_at": r.started_at.isoformat() if r.started_at else None,
                }
                for r in runs
            ]

        seed_info: dict[str, Any] | None = None
        seed_checksum_path = Path(__file__).resolve().parent.parent / "data" / "seed" / "checksums.json"
        if seed_checksum_path.exists():
            with open(seed_checksum_path, encoding="utf-8") as f:
                seed_info = json.load(f)

        return {
            "status": "ready",
            "backend": engine.dialect.name,
            "database_url": str(engine.url),
            "tables": list(Base.metadata.tables.keys()),
            "row_counts": {
                "actual_wind": actual_count,
                "wind_forecast": forecast_count,
            },
            "cache": analytics_service.cache_stats().model_dump(),
            "recent_ingest_runs": recent_runs,
            "seed_snapshot": seed_info,
            "parsers": {
                "FUELHH": {
                    "status": "verified" if fuelhh_rejected == 0 else "degraded",
                    "parsed_valid": fuelhh_valid,
                    "rejected": fuelhh_rejected,
                },
                "WINDFOR": {
                    "status": "verified" if windfor_rejected == 0 else "degraded",
                    "parsed_valid": windfor_valid,
                    "rejected": windfor_rejected,
                },
            },
        }

    @app.get("/api/v1/day-ahead", response_model=DayAheadResult, tags=["Analytics"])
    async def get_day_ahead(
        decision_date: str = Query(
            default="2026-01-01",
            description="Decision date on D-1 (YYYY-MM-DD)",
            pattern=r"^\d{4}-\d{2}-\d{2}$",
        ),
        cutoff: str = Query(
            default="09:00",
            description="Cut-off time on D-1 in London local time (HH:MM)",
            pattern=r"^\d{2}:\d{2}$",
        ),
    ) -> DayAheadResult:
        """
        Evaluate day-ahead wind forecast for delivery day (decision_date + 1 day).
        Selects latest forecast vintage available at or before cutoff on decision_date,
        pairs with actual delivered wind generation, and calculates error and coverage.
        """
        try:
            d_date = date.fromisoformat(decision_date)
        except ValueError as err:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid decision_date format (expected YYYY-MM-DD): {decision_date}",
            ) from err

        try:
            parts = cutoff.split(":")
            h, m = int(parts[0]), int(parts[1])
            if not (0 <= h <= 23 and 0 <= m <= 59):
                raise ValueError("Out of range")
        except ValueError as err:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid cutoff time format (expected HH:MM between 00:00 and 23:59): {cutoff}",
            ) from err

        with SessionLocal() as session:
            return analytics_service.get_day_ahead(session, d_date, cutoff_str=cutoff)

    @app.get("/api/v1/day-ahead/vintages", response_model=DayAheadVintagesResult, tags=["Analytics"])
    async def get_day_ahead_vintages_endpoint(
        delivery_date: str = Query(
            default="2026-01-15",
            description="Target electricity delivery date (YYYY-MM-DD)",
            pattern=r"^\d{4}-\d{2}-\d{2}$",
        ),
        limit_vintages: int | None = Query(
            default=None,
            ge=1,
            le=100,
            description="Optional limit to return latest/sampled N vintages",
        ),
    ) -> DayAheadVintagesResult:
        """
        All published forecast vintages and delivered actuals for one delivery day (FR-VINTAGES).
        Orders vintage curves chronologically to evaluate forecast trajectory evolution.
        """
        try:
            d_date = date.fromisoformat(delivery_date)
        except ValueError as err:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid delivery_date format (expected YYYY-MM-DD): {delivery_date}",
            ) from err

        with SessionLocal() as session:
            return analytics_service.get_day_ahead_vintages(
                session, d_date, limit_vintages=limit_vintages
            )

    @app.get("/api/v1/accuracy/summary", response_model=AccuracySummaryResult, tags=["Analytics"])
    async def get_accuracy_summary_endpoint(
        from_date: str | None = Query(default=None, alias="from", description="Start decision date (YYYY-MM-DD)"),
        to_date: str | None = Query(default=None, alias="to", description="End decision date (YYYY-MM-DD)"),
        decision_from: str | None = Query(default=None, description="Start decision date alias (YYYY-MM-DD)"),
        decision_to: str | None = Query(default=None, description="End decision date alias (YYYY-MM-DD)"),
        cutoff: str = Query(default="09:00", description="Cut-off time on D-1 in London local time (HH:MM)", pattern=r"^\d{2}:\d{2}$"),
    ) -> AccuracySummaryResult:
        """
        Headline quantitative accuracy metrics (Bias, MAE, RMSE, WAPE, quantiles, shortfall stats)
        for day-ahead forecasts across a window of decision days.
        """
        start_str = from_date or decision_from or "2026-01-01"
        end_str = to_date or decision_to or "2026-01-31"

        try:
            d_from = date.fromisoformat(start_str)
            d_to = date.fromisoformat(end_str)
        except ValueError as err:
            raise HTTPException(status_code=400, detail=f"Invalid date format: {err}") from err

        if d_from > d_to:
            raise HTTPException(status_code=400, detail="from date cannot be after to date")

        try:
            parts = cutoff.split(":")
            h, m = int(parts[0]), int(parts[1])
            if not (0 <= h <= 23 and 0 <= m <= 59):
                raise ValueError("Out of range")
        except ValueError as err:
            raise HTTPException(status_code=400, detail=f"Invalid cutoff time format: {cutoff}") from err

        with SessionLocal() as session:
            return analytics_service.get_accuracy_summary(session, d_from, d_to, cutoff_str=cutoff)

    @app.get("/api/v1/accuracy/distribution", response_model=DistributionResult, tags=["Analytics"])
    async def get_accuracy_distribution_endpoint(
        from_date: str | None = Query(default=None, alias="from", description="Start decision date (YYYY-MM-DD)"),
        to_date: str | None = Query(default=None, alias="to", description="End decision date (YYYY-MM-DD)"),
        decision_from: str | None = Query(default=None, description="Start decision date alias (YYYY-MM-DD)"),
        decision_to: str | None = Query(default=None, description="End decision date alias (YYYY-MM-DD)"),
        cutoff: str = Query(default="09:00", description="Cut-off time on D-1 in London local time (HH:MM)", pattern=r"^\d{2}:\d{2}$"),
        bins: int = Query(default=20, ge=5, le=100, description="Number of histogram bins"),
    ) -> DistributionResult:
        """
        Error distribution histogram and quantiles (P5 through P95) for day-ahead forecast errors.
        """
        start_str = from_date or decision_from or "2026-01-01"
        end_str = to_date or decision_to or "2026-01-31"

        try:
            d_from = date.fromisoformat(start_str)
            d_to = date.fromisoformat(end_str)
        except ValueError as err:
            raise HTTPException(status_code=400, detail=f"Invalid date format: {err}") from err

        if d_from > d_to:
            raise HTTPException(status_code=400, detail="from date cannot be after to date")

        try:
            parts = cutoff.split(":")
            h, m = int(parts[0]), int(parts[1])
            if not (0 <= h <= 23 and 0 <= m <= 59):
                raise ValueError("Out of range")
        except ValueError as err:
            raise HTTPException(status_code=400, detail=f"Invalid cutoff time format: {cutoff}") from err

        with SessionLocal() as session:
            return analytics_service.get_error_distribution(
                session, d_from, d_to, cutoff_str=cutoff, bins_count=bins
            )

    @app.get("/api/v1/accuracy/by-day", response_model=BreakdownResult, tags=["Analytics"])
    async def get_accuracy_by_day_endpoint(
        from_date: str | None = Query(default=None, alias="from"),
        to_date: str | None = Query(default=None, alias="to"),
        decision_from: str | None = Query(default=None),
        decision_to: str | None = Query(default=None),
        cutoff: str = Query(default="09:00", pattern=r"^\d{2}:\d{2}$"),
    ) -> BreakdownResult:
        """Breakdown of forecast accuracy metrics by delivery day."""
        start_str = from_date or decision_from or "2026-01-01"
        end_str = to_date or decision_to or "2026-01-31"
        try:
            d_from, d_to = date.fromisoformat(start_str), date.fromisoformat(end_str)
        except ValueError as err:
            raise HTTPException(status_code=400, detail=f"Invalid date format: {err}") from err
        if d_from > d_to:
            raise HTTPException(status_code=400, detail="from date cannot be after to date")

        with SessionLocal() as session:
            return analytics_service.get_breakdown(session, "day", d_from, d_to, cutoff_str=cutoff)

    @app.get("/api/v1/accuracy/by-hour", response_model=BreakdownResult, tags=["Analytics"])
    async def get_accuracy_by_hour_endpoint(
        from_date: str | None = Query(default=None, alias="from"),
        to_date: str | None = Query(default=None, alias="to"),
        decision_from: str | None = Query(default=None),
        decision_to: str | None = Query(default=None),
        cutoff: str = Query(default="09:00", pattern=r"^\d{2}:\d{2}$"),
    ) -> BreakdownResult:
        """Breakdown of forecast accuracy metrics by hour of day (0..23)."""
        start_str = from_date or decision_from or "2026-01-01"
        end_str = to_date or decision_to or "2026-01-31"
        try:
            d_from, d_to = date.fromisoformat(start_str), date.fromisoformat(end_str)
        except ValueError as err:
            raise HTTPException(status_code=400, detail=f"Invalid date format: {err}") from err
        if d_from > d_to:
            raise HTTPException(status_code=400, detail="from date cannot be after to date")

        with SessionLocal() as session:
            return analytics_service.get_breakdown(session, "hour", d_from, d_to, cutoff_str=cutoff)

    @app.get("/api/v1/accuracy/by-horizon", response_model=BreakdownResult, tags=["Analytics"])
    async def get_accuracy_by_horizon_endpoint(
        from_date: str | None = Query(default=None, alias="from"),
        to_date: str | None = Query(default=None, alias="to"),
        decision_from: str | None = Query(default=None),
        decision_to: str | None = Query(default=None),
        cutoff: str = Query(default="09:00", pattern=r"^\d{2}:\d{2}$"),
    ) -> BreakdownResult:
        """Breakdown of forecast accuracy metrics by forecast lead time horizon buckets."""
        start_str = from_date or decision_from or "2026-01-01"
        end_str = to_date or decision_to or "2026-01-31"
        try:
            d_from, d_to = date.fromisoformat(start_str), date.fromisoformat(end_str)
        except ValueError as err:
            raise HTTPException(status_code=400, detail=f"Invalid date format: {err}") from err
        if d_from > d_to:
            raise HTTPException(status_code=400, detail="from date cannot be after to date")

        with SessionLocal() as session:
            return analytics_service.get_breakdown(session, "horizon", d_from, d_to, cutoff_str=cutoff)

    @app.get("/api/v1/accuracy/by-level", response_model=BreakdownResult, tags=["Analytics"])
    async def get_accuracy_by_level_endpoint(
        from_date: str | None = Query(default=None, alias="from"),
        to_date: str | None = Query(default=None, alias="to"),
        decision_from: str | None = Query(default=None),
        decision_to: str | None = Query(default=None),
        cutoff: str = Query(default="09:00", pattern=r"^\d{2}:\d{2}$"),
    ) -> BreakdownResult:
        """Breakdown of forecast accuracy metrics by forecast wind power level tiers."""
        start_str = from_date or decision_from or "2026-01-01"
        end_str = to_date or decision_to or "2026-01-31"
        try:
            d_from, d_to = date.fromisoformat(start_str), date.fromisoformat(end_str)
        except ValueError as err:
            raise HTTPException(status_code=400, detail=f"Invalid date format: {err}") from err
        if d_from > d_to:
            raise HTTPException(status_code=400, detail="from date cannot be after to date")

        with SessionLocal() as session:
            return analytics_service.get_breakdown(session, "level", d_from, d_to, cutoff_str=cutoff)

    @app.get("/api/v1/accuracy/buffer", response_model=ProcurementBufferResult, tags=["Analytics"])
    async def get_procurement_buffer_endpoint(
        from_date: str | None = Query(default=None, alias="from"),
        to_date: str | None = Query(default=None, alias="to"),
        decision_from: str | None = Query(default=None),
        decision_to: str | None = Query(default=None),
        cutoff: str = Query(default="09:00", pattern=r"^\d{2}:\d{2}$"),
        confidence: float = Query(default=0.90, ge=0.50, le=0.99, description="Confidence level (0.50 to 0.99)"),
    ) -> ProcurementBufferResult:
        """
        Procurement safety buffer calculation for requested confidence level c.
        Returns overall safety buffer MW and hourly buffer profile to derive risk-adjusted wind.
        """
        start_str = from_date or decision_from or "2026-01-01"
        end_str = to_date or decision_to or "2026-01-31"
        try:
            d_from, d_to = date.fromisoformat(start_str), date.fromisoformat(end_str)
        except ValueError as err:
            raise HTTPException(status_code=400, detail=f"Invalid date format: {err}") from err
        if d_from > d_to:
            raise HTTPException(status_code=400, detail="from date cannot be after to date")

        with SessionLocal() as session:
            return analytics_service.get_procurement_buffer(
                session, d_from, d_to, cutoff_str=cutoff, confidence=confidence
            )

    @app.get("/api/v1/accuracy/horizon-curve", response_model=HorizonCurveResult, tags=["Analytics"])
    async def get_horizon_curve_endpoint(
        from_date: str | None = Query(default=None, alias="from", description="Delivery start date (YYYY-MM-DD)"),
        to_date: str | None = Query(default=None, alias="to", description="Delivery end date (YYYY-MM-DD)"),
        delivery_from: str | None = Query(default=None, description="Delivery start date alias (YYYY-MM-DD)"),
        delivery_to: str | None = Query(default=None, description="Delivery end date alias (YYYY-MM-DD)"),
        max_horizon: int = Query(default=48, ge=6, le=168, description="Maximum forecast horizon hours"),
        step: int = Query(default=6, ge=1, le=24, description="Horizon step bucket width in hours"),
    ) -> HorizonCurveResult:
        """
        All-vintages forecast error degradation curve as a function of lead horizon (FR-ACC-5).
        Evaluates Bias, MAE, RMSE, and Shortfall Frequency across all published vintages from 0h to 48h+.
        """
        start_str = from_date or delivery_from or "2026-01-01"
        end_str = to_date or delivery_to or "2026-01-31"
        try:
            d_from, d_to = date.fromisoformat(start_str), date.fromisoformat(end_str)
        except ValueError as err:
            raise HTTPException(status_code=400, detail=f"Invalid date format: {err}") from err
        if d_from > d_to:
            raise HTTPException(status_code=400, detail="from date cannot be after to date")

        with SessionLocal() as session:
            return analytics_service.get_horizon_curve(
                session, d_from, d_to, max_horizon_h=max_horizon, step_hours=step
            )

    @app.get("/api/v1/accuracy/benchmark", response_model=PersistenceBenchmarkResult, tags=["Analytics"])
    async def get_persistence_benchmark_endpoint(
        from_date: str | None = Query(default=None, alias="from", description="Start decision date (YYYY-MM-DD)"),
        to_date: str | None = Query(default=None, alias="to", description="End decision date (YYYY-MM-DD)"),
        decision_from: str | None = Query(default=None, description="Start decision date alias (YYYY-MM-DD)"),
        decision_to: str | None = Query(default=None, description="End decision date alias (YYYY-MM-DD)"),
        cutoff: str = Query(
            default="09:00",
            description="Decision cut-off time on D-1 in London local time (HH:MM)",
            pattern=r"^\d{2}:\d{2}$",
        ),
    ) -> PersistenceBenchmarkResult:
        """
        Naive 24-hour persistence baseline benchmark and forecast skill score evaluation (FR-ACC-6).
        Compares day-ahead forecasts against actual generation from t - 24h, calculating
        comparative MAE, RMSE, Bias, and WMO Skill Score: 1 - (MAE_forecast / MAE_persistence).
        """
        start_str = from_date or decision_from or "2026-01-01"
        end_str = to_date or decision_to or "2026-01-31"
        try:
            d_from = date.fromisoformat(start_str)
            d_to = date.fromisoformat(end_str)
        except ValueError as err:
            raise HTTPException(status_code=400, detail=f"Invalid date format: {err}") from err
        if d_from > d_to:
            raise HTTPException(status_code=400, detail="from date cannot be after to date")

        try:
            parts = cutoff.split(":")
            h, m = int(parts[0]), int(parts[1])
            if not (0 <= h <= 23 and 0 <= m <= 59):
                raise ValueError("Out of range")
        except ValueError as err:
            raise HTTPException(status_code=400, detail=f"Invalid cutoff time format: {cutoff}") from err

        with SessionLocal() as session:
            return analytics_service.get_persistence_benchmark(
                session, d_from, d_to, cutoff_str=cutoff
            )

    @app.get("/api/v1/export/day-ahead.csv", tags=["Export"])
    async def export_day_ahead_csv_endpoint(
        from_date: str | None = Query(default=None, alias="from", description="Start decision date (YYYY-MM-DD)"),
        to_date: str | None = Query(default=None, alias="to", description="End decision date (YYYY-MM-DD)"),
        decision_from: str | None = Query(default=None, description="Start decision date alias (YYYY-MM-DD)"),
        decision_to: str | None = Query(default=None, description="End decision date alias (YYYY-MM-DD)"),
        delivery_date: str | None = Query(default=None, description="Single target delivery date (YYYY-MM-DD)"),
        cutoff: str = Query(
            default="09:00",
            description="Decision cut-off time on D-1 in London local time (HH:MM)",
            pattern=r"^\d{2}:\d{2}$",
        ),
    ) -> StreamingResponse:
        """
        RFC 4180 streaming CSV export for day-ahead wind generation forecasts and actuals (FR-API-4).
        Returns a streaming file attachment with CRLF line endings and complete 30-minute settlement period schedules.
        """
        if delivery_date:
            try:
                del_d = date.fromisoformat(delivery_date)
                d_from = del_d - timedelta(days=1)
                d_to = del_d - timedelta(days=1)
            except ValueError as err:
                raise HTTPException(status_code=400, detail=f"Invalid delivery_date format: {err}") from err
        else:
            start_str = from_date or decision_from or "2026-01-01"
            end_str = to_date or decision_to or "2026-01-31"
            try:
                d_from = date.fromisoformat(start_str)
                d_to = date.fromisoformat(end_str)
            except ValueError as err:
                raise HTTPException(status_code=400, detail=f"Invalid date format: {err}") from err
            if d_from > d_to:
                raise HTTPException(status_code=400, detail="from date cannot be after to date")

        try:
            parts = cutoff.split(":")
            h, m = int(parts[0]), int(parts[1])
            if not (0 <= h <= 23 and 0 <= m <= 59):
                raise ValueError("Out of range")
        except ValueError as err:
            raise HTTPException(status_code=400, detail=f"Invalid cutoff time format: {cutoff}") from err

        filename = get_export_filename(d_from, d_to, cutoff)

        def iter_csv() -> Generator[str, None, None]:
            with SessionLocal() as session:
                yield from stream_day_ahead_csv(session, d_from, d_to, cutoff_str=cutoff)

        return StreamingResponse(
            iter_csv(),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @app.get("/api/v1/analytics/cache/stats", response_model=CacheStats, tags=["System"])
    async def get_cache_stats_endpoint() -> CacheStats:
        """Operational statistics for in-memory analytics caching."""
        return analytics_service.cache_stats()

    @app.post("/api/v1/analytics/cache/invalidate", tags=["System"])
    async def invalidate_cache_endpoint() -> dict[str, str]:
        """Invalidate all cached analytical responses."""
        analytics_service.invalidate_cache()
        return {"status": "cache_invalidated"}

    # Mount static front-end assets if present (frontend/dist, Docker container /app/static, or demo-ui)
    base_dir = Path(__file__).resolve().parent.parent
    static_dirs = [
        base_dir / "static",
        base_dir.parent / "frontend" / "dist",
        base_dir.parent / "demo-ui",
        base_dir / "demo-ui",
    ]
    for s_dir in static_dirs:
        if s_dir.exists() and (s_dir / "index.html").exists():
            app.mount("/", StaticFiles(directory=str(s_dir), html=True), name="static")
            logger.info("mounted_static_ui", directory=str(s_dir))
            break

    return app


app = create_app()

