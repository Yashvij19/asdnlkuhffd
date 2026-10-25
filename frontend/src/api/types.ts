// Types for Wind Generation Forecast Monitor API and UI state

export interface SettlementPeriodRecord {
  period: number;             // Settlement period 1..48
  start_time: string;         // e.g. "00:00"
  end_time: string;           // e.g. "00:30"
  forecast_mw: number;        // Forecast at cut-off
  forecast_publish_time?: string; // e.g. "2026-01-15T08:00:00Z"
  horizon_hours?: number;     // Lead time from publication to settlement
  actual_mw: number | null;   // Actual metered generation (null if unmetered)
  error_mw: number | null;    // Signed error: actual_mw - forecast_mw (or forecast_mw - actual_mw)
  error_pct: number | null;   // Error as % of actual or forecast
  is_shortfall: boolean;      // True if actual < forecast
  buffer_p90_mw?: number;     // Recommended safety buffer for this period
}

export interface DayAheadResult {
  decision_date: string;       // YYYY-MM-DD
  delivery_date: string;       // YYYY-MM-DD
  cutoff_time: string;         // HH:MM (London time)
  selected_vintage_time: string; // Publish timestamp of chosen forecast
  forecast_age_hours: number;  // Hours between forecast publication and cutoff
  total_periods: number;       // usually 48
  available_periods: number;   // e.g. 48
  coverage_pct: number;        // 100.0%
  expected_avg_mw: number;     // e.g. 8420 MW
  total_delivery_mwh: number;  // e.g. 202080 MWh
  lowest_period: {
    period: number;
    time: string;
    forecast_mw: number;
    actual_mw?: number;
  };
  highest_period: {
    period: number;
    time: string;
    forecast_mw: number;
    actual_mw?: number;
  };
  buffer_recommended_mw: number; // e.g. 410 MW at 90% confidence
  buffer_total_mwh: number;      // e.g. 9840 MWh
  summary_metrics: {
    mae_mw: number;            // Mean Absolute Error
    bias_mw: number;           // Signed Mean Bias (+ indicates over-forecasting)
    rmse_mw: number;           // Root Mean Square Error
    worst_shortfall_period: number;
    worst_shortfall_mw: number;
    shortfall_periods_count: number;
    surplus_periods_count: number;
  };
  records: SettlementPeriodRecord[];
}

export interface VintageCurve {
  vintage_id: string;
  publish_time: string;
  label: string;
  is_selected_at_cutoff: boolean;
  is_post_cutoff: boolean;
  periods: { period: number; forecast_mw: number }[];
}

export interface DayAheadVintagesResult {
  delivery_date: string;
  cutoff_time: string;
  selected_vintage_publish_time: string;
  vintages: VintageCurve[];
  actuals: { period: number; actual_mw: number }[];
}

export interface AccuracySummaryResult {
  evaluation_window: {
    from_date: string;
    to_date: string;
    cutoff: string;
    settlement_periods_count: number;
    days_count: number;
  };
  mae_mw: number;
  bias_mw: number;
  rmse_mw: number;
  wape_pct: number;
  shortfall_frequency_pct: number;
  mean_shortfall_mw: number;
  max_shortfall_mw: number;
  max_shortfall_period_info: {
    date: string;
    period: number;
    time: string;
    shortfall_mw: number;
    event_label?: string;
  };
  coverage_pct: number;
  persistence_benchmark: {
    persistence_mae_mw: number;
    skill_improvement_pct: number;
  };
}

export interface DailyAccuracyRecord {
  date: string;
  mae_mw: number;
  bias_mw: number;
  rmse_mw: number;
  shortfall_frequency_pct: number;
  shortfall_periods_count: number;
  max_shortfall_mw: number;
  total_periods: number;
}

export interface HourlyErrorRecord {
  hour: number;               // 0..23
  time_label: string;         // "00:00", "01:00"
  mae_mw: number;
  bias_mw: number;
  p90_shortfall_mw: number;
  is_peak_window: boolean;
}

export interface HorizonDegradationRecord {
  horizon_hours: number;      // 1, 6, 12, 18, 24, 36, 48
  mae_mw: number;
  bias_mw: number;
  records_count: number;
}

export interface ErrorDistributionBin {
  bin_center_mw: number;
  bin_min_mw: number;
  bin_max_mw: number;
  count: number;
  is_shortfall_tail: boolean;
}

export interface DistributionResult {
  p5_mw: number;
  p10_mw: number;
  p25_mw: number;
  p50_median_mw: number;
  p75_mw: number;
  p90_mw: number;
  p95_mw: number;
  bins: ErrorDistributionBin[];
}

export interface BufferCalibrationData {
  confidence_pct: number;     // 80, 90, 95, 99
  baseline_buffer_mw: number;
  morning_ramp_buffer_mw: number;
  afternoon_trough_buffer_mw: number;
  evening_peak_buffer_mw: number;
  night_baseline_buffer_mw: number;
  mitigation_effectiveness_pct: number;
}
