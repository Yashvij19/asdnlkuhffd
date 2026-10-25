"""
Ingestion orchestrator, idempotent upserts, run auditing, and seed snapshot management.
Supports programmatic execution and CLI invocation (python -m app.ingest).
"""

import argparse
import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import SessionLocal, init_db
from app.elexon.client import ElexonClient
from app.elexon.parsers import parse_fuelhh_batch, parse_windfor_batch
from app.logging import get_logger, setup_logging
from app.models import ActualWind, IngestRun, WindForecast
from app.schemas import ActualWindCreate, WindForecastCreate

logger = get_logger("app.ingest")


def upsert_actual_wind(session: Session, records: list[ActualWindCreate]) -> int:
    """Idempotently insert or update ActualWind records in bulk."""
    if not records:
        return 0

    now = datetime.now(UTC)
    values = [
        {
            "start_time_utc": r.start_time_utc,
            "settlement_date": r.settlement_date,
            "settlement_period": r.settlement_period,
            "generation_mw": r.generation_mw,
            "source_publish_time_utc": r.source_publish_time_utc,
            "ingested_at": now,
        }
        for r in records
    ]

    # SQLite dialect bulk upsert with ON CONFLICT DO UPDATE in chunks of 500
    chunk_size = 500
    for i in range(0, len(values), chunk_size):
        chunk = values[i : i + chunk_size]
        stmt = sqlite_insert(ActualWind).values(chunk)
        update_cols = {
            "settlement_date": stmt.excluded.settlement_date,
            "settlement_period": stmt.excluded.settlement_period,
            "generation_mw": stmt.excluded.generation_mw,
            "source_publish_time_utc": stmt.excluded.source_publish_time_utc,
            "ingested_at": stmt.excluded.ingested_at,
        }
        upsert_stmt = stmt.on_conflict_do_update(
            index_elements=[ActualWind.start_time_utc],
            set_=update_cols,
        )
        session.execute(upsert_stmt)

    session.commit()
    return len(records)


def upsert_wind_forecast(session: Session, records: list[WindForecastCreate]) -> int:
    """Idempotently insert or update WindForecast records in bulk."""
    if not records:
        return 0

    now = datetime.now(UTC)
    values = [
        {
            "start_time_utc": r.start_time_utc,
            "publish_time_utc": r.publish_time_utc,
            "generation_mw": r.generation_mw,
            "horizon_hours": r.horizon_hours,
            "ingested_at": now,
        }
        for r in records
    ]

    # SQLite dialect bulk upsert with ON CONFLICT DO UPDATE in chunks of 500
    chunk_size = 500
    for i in range(0, len(values), chunk_size):
        chunk = values[i : i + chunk_size]
        stmt = sqlite_insert(WindForecast).values(chunk)
        update_cols = {
            "generation_mw": stmt.excluded.generation_mw,
            "horizon_hours": stmt.excluded.horizon_hours,
            "ingested_at": stmt.excluded.ingested_at,
        }
        upsert_stmt = stmt.on_conflict_do_update(
            index_elements=[WindForecast.start_time_utc, WindForecast.publish_time_utc],
            set_=update_cols,
        )
        session.execute(upsert_stmt)

    session.commit()
    return len(records)


def ingest_fuelhh(
    session: Session,
    start_date: date,
    end_date: date,
    client: ElexonClient | None = None,
) -> IngestRun:
    """Fetch, parse, validate, and upsert FUELHH wind actuals for the given settlement date range."""
    elexon = client or ElexonClient()
    settings = get_settings()

    run = IngestRun(
        started_at=datetime.now(UTC),
        status="running",
        dataset="FUELHH",
        range_from=start_date.isoformat(),
        range_to=end_date.isoformat(),
    )
    session.add(run)
    session.commit()

    try:
        raw_rows = elexon.fetch_fuelhh_range(
            start_date=start_date,
            end_date=end_date,
            chunk_days=settings.chunk_days,
        )
        run.rows_fetched = len(raw_rows)

        parsed = parse_fuelhh_batch(raw_rows)
        run.rows_rejected = parsed.rejected_count

        upserted_count = upsert_actual_wind(session, parsed.valid_rows)
        run.rows_upserted = upserted_count

        run.status = "partial" if run.rows_rejected > 0 else "success"
        run.finished_at = datetime.now(UTC)
        session.commit()
        logger.info(
            "fuelhh_ingest_completed",
            fetched=run.rows_fetched,
            upserted=run.rows_upserted,
            rejected=run.rows_rejected,
            status=run.status,
        )
        return run
    except Exception as err:
        session.rollback()
        run.status = "failed"
        run.error = str(err)
        run.finished_at = datetime.now(UTC)
        session.commit()
        logger.error("fuelhh_ingest_failed", error=str(err))
        raise


def ingest_windfor(
    session: Session,
    start_dt: datetime,
    end_dt: datetime,
    client: ElexonClient | None = None,
) -> IngestRun:
    """Fetch, parse, validate, and upsert WINDFOR forecasts published within the given datetime window."""
    elexon = client or ElexonClient()
    settings = get_settings()

    run = IngestRun(
        started_at=datetime.now(UTC),
        status="running",
        dataset="WINDFOR",
        range_from=start_dt.isoformat(),
        range_to=end_dt.isoformat(),
    )
    session.add(run)
    session.commit()

    try:
        raw_rows = elexon.fetch_windfor_range(
            start_dt=start_dt,
            end_dt=end_dt,
            chunk_days=settings.chunk_days,
        )
        run.rows_fetched = len(raw_rows)

        parsed = parse_windfor_batch(raw_rows)
        run.rows_rejected = parsed.rejected_count

        upserted_count = upsert_wind_forecast(session, parsed.valid_rows)
        run.rows_upserted = upserted_count

        run.status = "partial" if run.rows_rejected > 0 else "success"
        run.finished_at = datetime.now(UTC)
        session.commit()
        logger.info(
            "windfor_ingest_completed",
            fetched=run.rows_fetched,
            upserted=run.rows_upserted,
            rejected=run.rows_rejected,
            status=run.status,
        )
        return run
    except Exception as err:
        session.rollback()
        run.status = "failed"
        run.error = str(err)
        run.finished_at = datetime.now(UTC)
        session.commit()
        logger.error("windfor_ingest_failed", error=str(err))
        raise


# Seed Snapshot Management
def compute_file_sha256(file_path: Path) -> str:
    """Compute hex SHA256 checksum for a file."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def create_seed_snapshot(session: Session, seed_dir: Path) -> dict[str, Any]:
    """Export all stored ActualWind and WindForecast data into committed seed snapshot files."""
    seed_dir.mkdir(parents=True, exist_ok=True)
    actuals_file = seed_dir / "seed_actuals.json"
    forecasts_file = seed_dir / "seed_forecasts.json"
    checksum_file = seed_dir / "checksums.json"

    # Export Actuals
    actuals = session.scalars(select(ActualWind).order_by(ActualWind.start_time_utc)).all()
    actuals_data = [
        {
            "start_time_utc": r.start_time_utc.isoformat(),
            "settlement_date": r.settlement_date,
            "settlement_period": r.settlement_period,
            "generation_mw": r.generation_mw,
            "source_publish_time_utc": r.source_publish_time_utc.isoformat(),
        }
        for r in actuals
    ]
    with open(actuals_file, "w", encoding="utf-8") as f:
        json.dump(actuals_data, f, indent=2)

    # Export Forecasts
    forecasts = session.scalars(select(WindForecast).order_by(WindForecast.start_time_utc)).all()
    forecasts_data = [
        {
            "start_time_utc": r.start_time_utc.isoformat(),
            "publish_time_utc": r.publish_time_utc.isoformat(),
            "generation_mw": r.generation_mw,
            "horizon_hours": r.horizon_hours,
        }
        for r in forecasts
    ]
    with open(forecasts_file, "w", encoding="utf-8") as f:
        json.dump(forecasts_data, f, indent=2)

    # Compute checksums
    checksums = {
        "seed_actuals.json": compute_file_sha256(actuals_file),
        "seed_forecasts.json": compute_file_sha256(forecasts_file),
        "actuals_count": len(actuals_data),
        "forecasts_count": len(forecasts_data),
        "generated_at": datetime.now(UTC).isoformat(),
    }
    with open(checksum_file, "w", encoding="utf-8") as f:
        json.dump(checksums, f, indent=2)

    logger.info("seed_snapshot_created", actuals=len(actuals_data), forecasts=len(forecasts_data))
    return checksums


def load_seed_snapshot(session: Session, seed_dir: Path | None = None) -> tuple[int, int]:
    """Load data from bundled seed snapshot files if database is unseeded."""
    target_dir = seed_dir or Path(__file__).resolve().parent.parent / "data" / "seed"
    actuals_file = target_dir / "seed_actuals.json"
    forecasts_file = target_dir / "seed_forecasts.json"
    checksum_file = target_dir / "checksums.json"

    if not actuals_file.exists() or not forecasts_file.exists():
        logger.info("seed_snapshot_not_found", dir=str(target_dir))
        return 0, 0

    # Verify checksums if present
    if checksum_file.exists():
        with open(checksum_file, encoding="utf-8") as f:
            checksums = json.load(f)
        if "seed_actuals.json" in checksums:
            assert compute_file_sha256(actuals_file) == checksums["seed_actuals.json"]
        if "seed_forecasts.json" in checksums:
            assert compute_file_sha256(forecasts_file) == checksums["seed_forecasts.json"]

    # Load Actuals
    with open(actuals_file, encoding="utf-8") as f:
        raw_actuals = json.load(f)
    actual_records = [
        ActualWindCreate(
            start_time_utc=datetime.fromisoformat(r["start_time_utc"]),
            settlement_date=r["settlement_date"],
            settlement_period=r["settlement_period"],
            generation_mw=r["generation_mw"],
            source_publish_time_utc=datetime.fromisoformat(r["source_publish_time_utc"]),
        )
        for r in raw_actuals
    ]
    upserted_actuals = upsert_actual_wind(session, actual_records)

    # Load Forecasts
    with open(forecasts_file, encoding="utf-8") as f:
        raw_forecasts = json.load(f)
    forecast_records = [
        WindForecastCreate(
            start_time_utc=datetime.fromisoformat(r["start_time_utc"]),
            publish_time_utc=datetime.fromisoformat(r["publish_time_utc"]),
            generation_mw=r["generation_mw"],
            horizon_hours=r["horizon_hours"],
        )
        for r in raw_forecasts
    ]
    upserted_forecasts = upsert_wind_forecast(session, forecast_records)

    logger.info("seed_snapshot_loaded", actuals=upserted_actuals, forecasts=upserted_forecasts)
    return upserted_actuals, upserted_forecasts


def seed_database_if_empty(session: Session) -> tuple[int, int]:
    """Check if the database has actuals, and if empty, automatically load the seed snapshot."""
    count = session.scalar(select(func.count()).select_from(ActualWind))
    if count == 0:
        logger.info("database_empty_loading_seed")
        return load_seed_snapshot(session)
    return 0, 0


def main() -> None:
    """CLI entrypoint for ingestion and seed management."""
    setup_logging()
    init_db()

    parser = argparse.ArgumentParser(description="Wind Generation Forecast Monitor Ingestion CLI")
    parser.add_argument("--seed", action="store_true", help="Load seed snapshot into database")
    parser.add_argument("--create-seed", action="store_true", help="Export database to seed snapshot files")
    parser.add_argument("--fuelhh", action="store_true", help="Fetch and ingest FUELHH actuals")
    parser.add_argument("--windfor", action="store_true", help="Fetch and ingest WINDFOR forecasts")
    parser.add_argument("--from-date", type=str, default="2026-01-01", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--to-date", type=str, default="2026-02-01", help="End date (YYYY-MM-DD)")

    args = parser.parse_args()
    seed_dir = Path(__file__).resolve().parent.parent / "data" / "seed"

    with SessionLocal() as session:
        if args.seed:
            a, f = load_seed_snapshot(session, seed_dir)
            print(f"Loaded seed snapshot: {a} actuals, {f} forecasts.")
        elif args.create_seed:
            checksums = create_seed_snapshot(session, seed_dir)
            print(f"Seed snapshot created: {checksums}")
        elif args.fuelhh:
            d_from = date.fromisoformat(args.from_date)
            d_to = date.fromisoformat(args.to_date)
            run = ingest_fuelhh(session, d_from, d_to)
            print(f"FUELHH Ingest Complete: {run.rows_upserted} upserted, {run.rows_rejected} rejected.")
        elif args.windfor:
            dt_from = datetime.fromisoformat(args.from_date).replace(tzinfo=UTC)
            dt_to = datetime.fromisoformat(args.to_date).replace(tzinfo=UTC)
            run = ingest_windfor(session, dt_from, dt_to)
            print(f"WINDFOR Ingest Complete: {run.rows_upserted} upserted, {run.rows_rejected} rejected.")
        else:
            parser.print_help()


if __name__ == "__main__":
    main()
