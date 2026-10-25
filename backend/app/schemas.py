"""
Pydantic v2 schemas for data validation, row parsing, and API responses.
"""

from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class ActualWindCreate(BaseModel):
    """Schema for validating and inserting a wind actual generation record."""

    model_config = ConfigDict(from_attributes=True)

    start_time_utc: datetime = Field(description="Period start time in UTC")
    settlement_date: str = Field(description="Settlement date in YYYY-MM-DD format")
    settlement_period: int = Field(ge=1, le=50, description="Settlement period number (1-50)")
    generation_mw: float = Field(ge=0.0, description="Wind generation in MW (non-negative)")
    source_publish_time_utc: datetime = Field(description="When Elexon published the actual in UTC")


class ActualWindRead(ActualWindCreate):
    """Schema for reading an actual wind record including ingestion metadata."""

    ingested_at: datetime


class WindForecastCreate(BaseModel):
    """Schema for validating and inserting a wind generation forecast vintage."""

    model_config = ConfigDict(from_attributes=True)

    start_time_utc: datetime = Field(description="Target period start time in UTC")
    publish_time_utc: datetime = Field(description="Forecast vintage publication time in UTC")
    generation_mw: float = Field(ge=0.0, description="Forecasted generation in MW (non-negative)")
    horizon_hours: float = Field(description="Lead time horizon in decimal hours")


class WindForecastRead(WindForecastCreate):
    """Schema for reading a forecast record including ingestion metadata."""

    ingested_at: datetime


class IngestRunCreate(BaseModel):
    """Schema for creating an ingestion audit log record."""

    model_config = ConfigDict(from_attributes=True)

    started_at: datetime
    status: str = Field(default="running", description="running | success | partial | failed")
    dataset: str = Field(description="FUELHH | WINDFOR | ALL")
    range_from: str
    range_to: str
    rows_fetched: int = 0
    rows_upserted: int = 0
    rows_rejected: int = 0
    error: str | None = None


class IngestRunRead(IngestRunCreate):
    """Schema for reading an ingestion audit log record."""

    id: int
    finished_at: datetime | None = None


class ParsedBatch(BaseModel, Generic[T]):
    """Container for batch parsing output including valid items and rejection details."""

    valid_rows: list[T]
    rejected_count: int
    rejections: list[str]


# ==============================================================================
# Day-Ahead Decision Schemas (Selection Algorithm Output)
# ==============================================================================


class DayAheadPoint(BaseModel):
    """A single 30-minute period comparison between latest day-ahead forecast and actual."""

    model_config = ConfigDict(from_attributes=True)

    start_time: datetime = Field(description="Settlement period start time in UTC")
    settlement_period: int = Field(ge=1, le=50, description="Settlement period (1-50)")
    forecast_mw: float | None = Field(default=None, description="Latest forecast available at cut-off (MW)")
    forecast_publish_time: datetime | None = Field(default=None, description="When selected vintage was published (UTC)")
    horizon_hours: float | None = Field(default=None, description="Lead time horizon in hours")
    actual_mw: float | None = Field(default=None, description="Actual wind generation delivered (MW)")
    error_mw: float | None = Field(default=None, description="Forecast error: actual - forecast (negative = shortfall)")


class DayAheadCoverage(BaseModel):
    """Data completeness and missing period reporting for a delivery day."""

    periods: int = Field(default=48, description="Expected settlement periods in delivery day")
    with_forecast: int = Field(description="Number of periods with a forecast available at cut-off")
    with_actual: int = Field(description="Number of periods with recorded actual generation")
    coverage_pct: float = Field(description="Percentage of periods with valid forecast")


class DayAheadSummary(BaseModel):
    """High-level summary metrics for a single delivery day."""

    forecast_mwh: float | None = Field(default=None, description="Total expected wind energy in MWh (MW * 0.5h)")
    actual_mwh: float | None = Field(default=None, description="Total delivered wind energy in MWh (MW * 0.5h)")
    mae_mw: float | None = Field(default=None, description="Mean Absolute Error in MW")
    bias_mw: float | None = Field(default=None, description="Mean error in MW: positive=over-delivered, negative=shortfall")


class DayAheadResult(BaseModel):
    """Complete day-ahead selection response for a given decision date and cut-off."""

    decision_date: str = Field(description="Date purchase decision was made (D-1, YYYY-MM-DD)")
    delivery_date: str = Field(description="Date electricity is delivered (D, YYYY-MM-DD)")
    cutoff_local: str = Field(description="Decision cut-off time in London local time (HH:MM)")
    cutoff_utc: datetime = Field(description="Exact cut-off timestamp in UTC")
    coverage: DayAheadCoverage
    summary: DayAheadSummary
    points: list[DayAheadPoint]


# ==============================================================================
# Accuracy Metrics Schemas (FR-ACC-1, FR-ACC-3)
# ==============================================================================


class AccuracyQuantiles(BaseModel):
    """Error quantiles (P5 through P95) of forecast error (actual - forecast) in MW."""

    p5: float = Field(description="5th percentile of error (MW)")
    p10: float = Field(description="10th percentile of error (MW)")
    p25: float = Field(description="25th percentile of error (Q1, MW)")
    p50: float = Field(description="50th percentile of error (Median, MW)")
    p75: float = Field(description="75th percentile of error (Q3, MW)")
    p90: float = Field(description="90th percentile of error (MW)")
    p95: float = Field(description="95th percentile of error (MW)")


class AccuracyMetrics(BaseModel):
    """Comprehensive headline quantitative accuracy metrics over an evaluation window."""

    evaluated_points: int = Field(description="Count of periods with both forecast and actual present")
    total_expected_periods: int = Field(description="Total settlement periods across delivery days")
    coverage_pct: float = Field(description="Coverage percentage of valid forecasts")
    bias_mw: float = Field(description="Mean error in MW (actual - forecast): positive=surplus, negative=shortfall")
    mae_mw: float = Field(description="Mean Absolute Error in MW: mean(|actual - forecast|)")
    rmse_mw: float = Field(description="Root Mean Squared Error in MW: sqrt(mean((actual - forecast)^2))")
    wape_pct: float = Field(description="Weighted Absolute Percentage Error: sum(|error|) / sum(actual) * 100")
    median_abs_error_mw: float = Field(description="Median absolute error in MW")
    p90_abs_error_mw: float = Field(description="90th percentile of absolute error in MW")
    shortfall_frequency_pct: float = Field(description="Percentage of periods where actual < forecast (error < 0)")
    mean_shortfall_mw: float = Field(description="Mean shortfall magnitude in MW for deficit periods (actual < forecast)")
    max_shortfall_mw: float = Field(description="Worst shortfall magnitude in MW (|min(error)| where error < 0)")
    max_surplus_mw: float = Field(description="Largest over-delivery in MW (max(error) where error > 0)")
    quantiles: AccuracyQuantiles


class AccuracySummaryResult(BaseModel):
    """Response schema for GET /api/v1/accuracy/summary."""

    decision_from: str = Field(description="Start of decision window (D-1, YYYY-MM-DD)")
    decision_to: str = Field(description="End of decision window (D-1, YYYY-MM-DD)")
    delivery_from: str = Field(description="Start of delivery window (D, YYYY-MM-DD)")
    delivery_to: str = Field(description="End of delivery window (D, YYYY-MM-DD)")
    cutoff_local: str = Field(description="Decision cut-off time in London local time (HH:MM)")
    days_evaluated: int = Field(description="Total days evaluated in window")
    metrics: AccuracyMetrics


class HistogramBin(BaseModel):
    """A single bucket in the error distribution histogram."""

    bin_start: float = Field(description="Left edge of error bin in MW (inclusive)")
    bin_end: float = Field(description="Right edge of error bin in MW (exclusive, except last bin)")
    bin_center: float = Field(description="Center point of error bin in MW")
    count: int = Field(description="Number of periods with forecast error falling in this bin")
    frequency_pct: float = Field(description="Percentage of total evaluated periods in this bin")


class DistributionResult(BaseModel):
    """Response schema for GET /api/v1/accuracy/distribution."""

    decision_from: str = Field(description="Start of decision window (D-1, YYYY-MM-DD)")
    decision_to: str = Field(description="End of decision window (D-1, YYYY-MM-DD)")
    cutoff_local: str = Field(description="Decision cut-off time in London local time (HH:MM)")
    total_samples: int = Field(description="Total count of evaluated settlement periods")
    min_error_mw: float = Field(description="Minimum error in MW (worst shortfall)")
    max_error_mw: float = Field(description="Maximum error in MW (largest surplus)")
    quantiles: AccuracyQuantiles
    bins: list[HistogramBin]


# ==============================================================================
# Breakdown & Procurement Buffer Schemas (FR-ACC-2, FR-ACC-4)
# ==============================================================================


class BreakdownPoint(BaseModel):
    """Aggregated performance metrics for a specific dimension slice."""

    dimension_key: str = Field(description="Key for slice (e.g. date YYYY-MM-DD, hour 00..23, horizon bucket, wind tier)")
    dimension_label: str = Field(description="Human-readable label for slice")
    count: int = Field(description="Number of evaluated periods in this slice")
    mean_forecast_mw: float = Field(description="Mean selected forecast generation in MW")
    mean_actual_mw: float = Field(description="Mean delivered generation in MW")
    bias_mw: float = Field(description="Mean error in MW: actual - forecast (negative = shortfall)")
    mae_mw: float = Field(description="Mean absolute error in MW")
    rmse_mw: float = Field(description="Root mean squared error in MW")
    wape_pct: float = Field(description="Weighted absolute percentage error (%)")
    shortfall_frequency_pct: float = Field(description="Percentage of periods where actual < forecast (%)")


class BreakdownResult(BaseModel):
    """Response schema for multi-dimensional breakdown queries."""

    dimension: str = Field(description="Dimension sliced on: day, hour, horizon, level, weekday_weekend")
    decision_from: str = Field(description="Start of decision window (D-1, YYYY-MM-DD)")
    decision_to: str = Field(description="End of decision window (D-1, YYYY-MM-DD)")
    cutoff_local: str = Field(description="Decision cut-off time in London local time (HH:MM)")
    items: list[BreakdownPoint]


class HourlyBufferPoint(BaseModel):
    """Procurement safety buffer for a single hour of day (0..23)."""

    hour: int = Field(ge=0, le=23, description="Hour of day (0-23)")
    hour_label: str = Field(description="Hour label (e.g. '08:00 - 09:00')")
    sample_count: int = Field(description="Number of evaluated samples for this hour")
    buffer_mw: float = Field(description="Safety buffer in MW to subtract from forecast at given confidence")
    mean_forecast_mw: float = Field(description="Historical mean forecast generation in MW")
    risk_adjusted_wind_mw: float = Field(description="Risk-adjusted wind: max(0, mean_forecast - buffer) in MW")


class ProcurementBufferResult(BaseModel):
    """Response schema for GET /api/v1/accuracy/buffer."""

    decision_from: str = Field(description="Start of decision window (D-1, YYYY-MM-DD)")
    decision_to: str = Field(description="End of decision window (D-1, YYYY-MM-DD)")
    cutoff_local: str = Field(description="Decision cut-off time in London local time (HH:MM)")
    confidence: float = Field(description="Requested confidence level (e.g. 0.90 for 90%)")
    confidence_pct: float = Field(description="Requested confidence percentage (e.g. 90.0%)")
    total_samples: int = Field(description="Total evaluated periods across window")
    overall_buffer_mw: float = Field(description="Overall safety buffer in MW: -quantile(error, 1 - c)")
    overall_mean_forecast_mw: float = Field(description="Overall historical mean forecast generation in MW")
    overall_risk_adjusted_mw: float = Field(description="Overall risk-adjusted wind: max(0, mean_forecast - buffer) in MW")
    hourly_buffers: list[HourlyBufferPoint]


# ==============================================================================
# Horizon Curve Schemas (FR-ACC-5) & Cache Schemas
# ==============================================================================


class HorizonCurvePoint(BaseModel):
    """Forecast accuracy metrics for a specific forecast lead horizon bucket across all vintages."""

    horizon_start_h: float = Field(description="Start of horizon bucket in hours (inclusive)")
    horizon_end_h: float = Field(description="End of horizon bucket in hours (exclusive)")
    bucket_label: str = Field(description="Display label (e.g. '0h - 6h' or '24h')")
    sample_count: int = Field(description="Number of vintage forecasts evaluated")
    mean_forecast_mw: float = Field(description="Mean forecasted generation in MW")
    mean_actual_mw: float = Field(description="Mean actual delivered generation in MW")
    bias_mw: float = Field(description="Mean error in MW: actual - forecast (negative = shortfall)")
    mae_mw: float = Field(description="Mean absolute error in MW")
    rmse_mw: float = Field(description="Root mean squared error in MW")
    wape_pct: float = Field(description="Weighted absolute percentage error (%)")
    shortfall_frequency_pct: float = Field(description="Percentage of vintage forecasts where actual < forecast (%)")


class HorizonCurveResult(BaseModel):
    """Response schema for GET /api/v1/accuracy/horizon-curve."""

    delivery_from: str = Field(description="Delivery date range start (YYYY-MM-DD)")
    delivery_to: str = Field(description="Delivery date range end (YYYY-MM-DD)")
    max_horizon_h: int = Field(description="Maximum lead horizon evaluated in hours")
    step_hours: int = Field(description="Bucket width in hours (e.g. 1 or 6)")
    total_samples: int = Field(description="Total vintage forecasts evaluated")
    curve: list[HorizonCurvePoint]


class CacheStats(BaseModel):
    """Operational diagnostics for in-memory analytics caching."""

    entries: int = Field(description="Total active cached query entries")
    hits: int = Field(description="Total cache hits")
    misses: int = Field(description="Total cache misses")
    hit_rate_pct: float = Field(description="Cache hit percentage")
    invalidations: int = Field(description="Total cache clears/invalidations")


# ==============================================================================
# Multi-Vintage Evolution Schemas (Phase 3.1)
# ==============================================================================


class VintageDataPoint(BaseModel):
    """Forecast generation for a single target period in a vintage series."""

    start_time: datetime = Field(description="Target period start time in UTC")
    settlement_period: int = Field(ge=1, le=50, description="Settlement period (1..48, up to 50 on clock change)")
    forecast_mw: float = Field(description="Forecasted wind generation in MW")
    horizon_hours: float = Field(description="Lead time horizon (target - publish) in hours")
    actual_mw: float | None = Field(default=None, description="Actual delivered generation if available")
    error_mw: float | None = Field(default=None, description="actual - forecast if actual available")


class VintageSeries(BaseModel):
    """A complete forecast curve issued at a specific publish timestamp."""

    publish_time_utc: datetime = Field(description="When this forecast vintage was published (UTC)")
    vintage_label: str = Field(description="Human-readable vintage identifier (e.g. 'Publish 2026-01-14 07:30 UTC')")
    points_count: int = Field(description="Count of target periods included in this vintage")
    mean_forecast_mw: float = Field(description="Mean forecasted power across covered target periods")
    mae_mw: float | None = Field(default=None, description="Mean Absolute Error of this vintage against actuals")
    bias_mw: float | None = Field(default=None, description="Mean Error (actual - forecast) of this vintage")
    points: list[VintageDataPoint]


class DayAheadVintagesResult(BaseModel):
    """Response schema for GET /api/v1/day-ahead/vintages."""

    delivery_date: str = Field(description="Target electricity delivery date (YYYY-MM-DD)")
    total_vintages_available: int = Field(description="Total distinct forecast vintages published for this day")
    returned_vintages: int = Field(description="Number of vintage curves returned")
    actuals: list[VintageDataPoint] = Field(description="Delivered actual generation for each target period")
    vintages: list[VintageSeries] = Field(description="Forecast curves ordered chronologically by publish time")


# ==============================================================================
# Persistence Baseline Benchmark Schemas (FR-ACC-6, Phase 3.2)
# ==============================================================================


class BenchmarkPoint(BaseModel):
    """Daily comparative accuracy and skill score evaluation."""

    delivery_date: str = Field(description="Delivery date (YYYY-MM-DD)")
    sample_count: int = Field(description="Evaluated settlement periods on this day")
    mean_actual_mw: float = Field(description="Mean delivered generation in MW")
    forecast_mean_mw: float = Field(description="Mean day-ahead forecast generation in MW")
    persistence_mean_mw: float = Field(description="Mean 24h naive persistence generation in MW")
    forecast_mae_mw: float = Field(description="Day-ahead forecast MAE in MW")
    persistence_mae_mw: float = Field(description="Naive 24h persistence MAE in MW")
    forecast_rmse_mw: float = Field(description="Day-ahead forecast RMSE in MW")
    persistence_rmse_mw: float = Field(description="Naive 24h persistence RMSE in MW")
    forecast_bias_mw: float = Field(description="Day-ahead forecast Bias (actual - forecast) in MW")
    persistence_bias_mw: float = Field(description="Naive 24h persistence Bias (actual - persistence) in MW")
    skill_score: float = Field(description="1 - (forecast_mae / persistence_mae). >0 indicates forecast outperforms baseline")
    skill_score_pct: float = Field(description="Skill score expressed as a percentage (%)")


class PersistenceBenchmarkResult(BaseModel):
    """Response schema for GET /api/v1/accuracy/benchmark."""

    decision_from: str = Field(description="Start of decision window (D-1, YYYY-MM-DD)")
    decision_to: str = Field(description="End of decision window (D-1, YYYY-MM-DD)")
    cutoff_local: str = Field(description="Decision cut-off time in London local time (HH:MM)")
    total_samples: int = Field(description="Total settlement periods evaluated across the window")
    overall_mean_actual_mw: float = Field(description="Mean actual wind generation across all evaluated periods")
    forecast_mae_mw: float = Field(description="Overall Day-Ahead Forecast MAE in MW")
    persistence_mae_mw: float = Field(description="Overall Naive 24h Persistence MAE in MW")
    forecast_rmse_mw: float = Field(description="Overall Day-Ahead Forecast RMSE in MW")
    persistence_rmse_mw: float = Field(description="Overall Naive 24h Persistence RMSE in MW")
    forecast_bias_mw: float = Field(description="Overall Day-Ahead Forecast Bias (actual - forecast) in MW")
    persistence_bias_mw: float = Field(description="Overall Naive 24h Persistence Bias in MW")
    overall_skill_score: float = Field(description="Overall skill score: 1 - (forecast_mae / persistence_mae)")
    overall_skill_score_pct: float = Field(description="Overall skill score percentage (%)")
    rmse_skill_score: float = Field(description="RMSE-based skill score: 1 - (forecast_rmse / persistence_rmse)")
    days_forecast_won: int = Field(description="Count of delivery days where forecast MAE was lower than persistence MAE")
    days_persistence_won: int = Field(description="Count of delivery days where persistence MAE was lower than or equal to forecast MAE")
    daily_comparison: list[BenchmarkPoint] = Field(description="Per-day comparative breakdown")




