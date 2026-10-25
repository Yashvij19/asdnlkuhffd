"""
SQLAlchemy 2.0 ORM models for Wind Generation Forecast Monitor.
Defines actual_wind, wind_forecast, and ingest_run tables.
"""

from datetime import UTC, datetime

from sqlalchemy import (
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class ActualWind(Base):
    """
    Actual national wind generation from Elexon FUELHH dataset (fuelType == WIND).
    Grain: One row per 30-minute settlement period (48 per full delivery day).
    """

    __tablename__ = "actual_wind"

    # Start of 30-minute settlement period in UTC
    start_time_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True, doc="Target settlement period start time (UTC)"
    )
    # Settlement date in YYYY-MM-DD
    settlement_date: Mapped[str] = mapped_column(
        String(10), nullable=False, index=True, doc="Settlement date (YYYY-MM-DD)"
    )
    # Settlement period (1-48, or 46/50 on clock change days)
    settlement_period: Mapped[int] = mapped_column(
        Integer, nullable=False, doc="Settlement period number (1-50)"
    )
    # Average power delivered over the 30-minute period in MW
    generation_mw: Mapped[float] = mapped_column(
        Float, nullable=False, doc="Generated wind power in MW"
    )
    # Source publish timestamp from Elexon BMRS in UTC
    source_publish_time_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, doc="When Elexon published the actual"
    )
    # Ingestion audit timestamp
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        doc="Record creation/upsert timestamp (UTC)",
    )

    def __repr__(self) -> str:
        return (
            f"<ActualWind(start_time={self.start_time_utc.isoformat()}, "
            f"period={self.settlement_period}, generation_mw={self.generation_mw})>"
        )


class WindForecast(Base):
    """
    Forecasted national wind generation from Elexon WINDFOR dataset.
    Grain: Multiple forecast vintages per target settlement period.
    Composite Key: (start_time_utc, publish_time_utc).
    """

    __tablename__ = "wind_forecast"

    # Target settlement period start time in UTC
    start_time_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True, doc="Target settlement period start time (UTC)"
    )
    # When the forecast vintage was created/published by Elexon
    publish_time_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True, doc="Forecast vintage publication time (UTC)"
    )
    # Forecasted wind power generation in MW
    generation_mw: Mapped[float] = mapped_column(
        Float, nullable=False, doc="Forecasted wind generation in MW"
    )
    # Horizon in hours: (start_time_utc - publish_time_utc) in decimal hours
    horizon_hours: Mapped[float] = mapped_column(
        Float, nullable=False, doc="Forecast lead time horizon in hours"
    )
    # Ingestion audit timestamp
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        doc="Record creation/upsert timestamp (UTC)",
    )

    __table_args__ = (
        # Optimized index for finding latest forecast before cut-off
        Index(
            "ix_wind_forecast_start_publish_desc",
            "start_time_utc",
            text("publish_time_utc DESC"),
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<WindForecast(target={self.start_time_utc.isoformat()}, "
            f"published={self.publish_time_utc.isoformat()}, "
            f"horizon={self.horizon_hours:.1f}h, mw={self.generation_mw})>"
        )


class IngestRun(Base):
    """
    Ingestion audit log tracking batch execution, counts, rejects, and errors.
    """

    __tablename__ = "ingest_run"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, doc="When the ingestion run began"
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, doc="When the ingestion run ended"
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, doc="running | success | partial | failed"
    )
    dataset: Mapped[str] = mapped_column(
        String(20), nullable=False, doc="FUELHH | WINDFOR | ALL"
    )
    range_from: Mapped[str] = mapped_column(
        String(35), nullable=False, doc="Date or datetime query lower bound"
    )
    range_to: Mapped[str] = mapped_column(
        String(35), nullable=False, doc="Date or datetime query upper bound"
    )
    rows_fetched: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, doc="Total raw rows returned by Elexon"
    )
    rows_upserted: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, doc="Total rows successfully stored or updated"
    )
    rows_rejected: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, doc="Total invalid rows discarded during validation"
    )
    error: Mapped[str | None] = mapped_column(
        Text, nullable=True, doc="Exception message or error details if failed"
    )

    def __repr__(self) -> str:
        return (
            f"<IngestRun(id={self.id}, dataset={self.dataset}, "
            f"status={self.status}, upserted={self.rows_upserted}, rejected={self.rows_rejected})>"
        )
