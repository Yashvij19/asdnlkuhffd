"""
Analytics and day-ahead forecast evaluation package.
"""

from app.analytics.benchmark import compute_persistence_benchmark
from app.analytics.breakdowns import (
    compute_breakdown_by_day,
    compute_breakdown_by_horizon,
    compute_breakdown_by_hour,
    compute_breakdown_by_level,
    compute_breakdown_by_weekday,
    format_breakdown_result,
)
from app.analytics.buffer import calculate_procurement_buffer
from app.analytics.export import get_export_filename, stream_day_ahead_csv
from app.analytics.metrics import (
    calculate_accuracy_metrics,
    calculate_error_distribution,
    compute_quantiles,
    evaluate_period_accuracy,
    get_accuracy_summary,
    get_error_distribution,
)
from app.analytics.selection import (
    compute_decision_cutoff_utc,
    get_delivery_day_periods,
    select_day_ahead_forecast,
)
from app.analytics.service import (
    AnalyticsCache,
    AnalyticsService,
    analytics_service,
    compute_all_vintages_horizon_curve,
)
from app.analytics.vintages import get_day_ahead_vintages

__all__ = [
    "AnalyticsCache",
    "AnalyticsService",
    "analytics_service",
    "calculate_accuracy_metrics",
    "calculate_error_distribution",
    "calculate_procurement_buffer",
    "compute_all_vintages_horizon_curve",
    "compute_breakdown_by_day",
    "compute_breakdown_by_horizon",
    "compute_breakdown_by_hour",
    "compute_breakdown_by_level",
    "compute_breakdown_by_weekday",
    "compute_decision_cutoff_utc",
    "compute_persistence_benchmark",
    "compute_quantiles",
    "evaluate_period_accuracy",
    "format_breakdown_result",
    "get_accuracy_summary",
    "get_day_ahead_vintages",
    "get_delivery_day_periods",
    "get_error_distribution",
    "get_export_filename",
    "select_day_ahead_forecast",
    "stream_day_ahead_csv",
]


