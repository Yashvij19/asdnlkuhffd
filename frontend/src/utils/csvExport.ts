import { DailyAccuracyRecord, DayAheadResult, HourlyErrorRecord } from '../api/types';

/**
 * Universal RFC 4180 compliant CSV export utility.
 * Includes UTF-8 BOM for Microsoft Excel compatibility and CRLF line terminators.
 */
export function downloadCsvFile(filename: string, csvContent: string): void {
  // Ensure filename has .csv extension
  const safeFilename = filename.toLowerCase().endsWith('.csv') ? filename : `${filename}.csv`;
  // UTF-8 BOM (\uFEFF) ensures Excel opens special characters, units, and commas cleanly
  const blob = new Blob(['\uFEFF' + csvContent], { type: 'text/csv;charset=utf-8;' });
  downloadBlob(safeFilename, blob);
}

/**
 * Universal text file download helper
 */
export function downloadTextFile(filename: string, content: string, mimeType = 'text/plain;charset=utf-8;'): void {
  const blob = new Blob([content], { type: mimeType });
  downloadBlob(filename, blob);
}

/**
 * Core download routine that guarantees Chromium / Edge respects the download filename
 */
function downloadBlob(filename: string, blob: Blob): void {
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.setAttribute('download', filename);
  link.rel = 'noopener';

  // Keep link in render tree off-screen so Chromium / Edge reliably parses
  // the `download` attribute before destruction (avoiding UUID fallback)
  link.style.position = 'fixed';
  link.style.top = '-9999px';
  link.style.left = '-9999px';
  link.style.opacity = '0';
  link.style.pointerEvents = 'none';

  document.body.appendChild(link);

  // Trigger download with synthetic mouse event for cross-browser reliability
  const clickEvent = new MouseEvent('click', {
    view: window,
    bubbles: true,
    cancelable: true,
  });
  link.dispatchEvent(clickEvent);

  // CRITICAL FIX: Chromium / Edge on Windows resolves the download filename asynchronously on its IO thread.
  // If the anchor element is removed from the DOM or the Object URL is revoked synchronously on the next line,
  // Chromium loses the `download` attribute and falls back to saving the raw Blob UUID (e.g. 'a360eb47-aebe...').
  // Keeping the element in the DOM and revoking after a 3000ms delay guarantees the file is saved with its proper
  // filename and `.csv` extension.
  setTimeout(() => {
    if (document.body.contains(link)) {
      document.body.removeChild(link);
    }
    window.URL.revokeObjectURL(url);
  }, 3000);
}

/**
 * Export Decision Brief (48 settlement periods)
 */
export function exportDecisionBriefCsv(data: DayAheadResult, cutoff: string = '09:00'): void {
  const headers = [
    'delivery_date',
    'settlement_period',
    'settlement_time_london',
    'cutoff_time',
    'forecast_mw',
    'actual_mw',
    'variance_error_mw',
    'variance_pct',
    'is_shortfall',
    'buffer_p90_recommended_mw',
  ];

  const rows = data.records.map((r) => [
    data.delivery_date,
    r.period,
    `"${r.start_time} - ${r.end_time}"`,
    cutoff,
    r.forecast_mw,
    r.actual_mw !== null ? r.actual_mw : '',
    r.error_mw !== null ? r.error_mw : '',
    r.error_pct !== null ? `${r.error_pct}%` : '',
    r.is_shortfall ? 'TRUE' : 'FALSE',
    data.buffer_recommended_mw,
  ]);

  const csvContent = [headers.join(','), ...rows.map((row) => row.join(','))].join('\r\n');
  const cleanDate = data.delivery_date.replace(/-/g, '');
  const cleanCutoff = cutoff.replace(':', '');
  downloadCsvFile(`wind_decision_brief_${cleanDate}_cutoff${cleanCutoff}.csv`, csvContent);
}

/**
 * Export Day Explorer (48 settlement periods with full reconciliation metadata)
 */
export function exportDayExplorerCsv(data: DayAheadResult, cutoff: string = '09:00'): void {
  const headers = [
    'delivery_date',
    'settlement_period',
    'start_time_london',
    'forecast_publish_vintage',
    'lead_time_hours',
    'day_ahead_forecast_mw',
    'outturn_actual_mw',
    'forecast_error_mw',
    'error_pct',
    'risk_status',
  ];

  const rows = data.records.map((r) => [
    data.delivery_date,
    r.period,
    r.start_time,
    r.forecast_publish_time || 'D-1 08:00',
    r.horizon_hours,
    r.forecast_mw,
    r.actual_mw !== null ? r.actual_mw : '',
    r.error_mw !== null ? r.error_mw : '',
    r.error_pct !== null ? `${r.error_pct}%` : '',
    r.is_shortfall ? 'Shortfall' : 'Surplus',
  ]);

  const csvContent = [headers.join(','), ...rows.map((row) => row.join(','))].join('\r\n');
  const cleanDate = data.delivery_date.replace(/-/g, '');
  downloadCsvFile(`day_ahead_settlement_reconciliation_${cleanDate}.csv`, csvContent);
}

/**
 * Export Accuracy 30-Day Benchmark
 */
export function exportAccuracyBenchmarkCsv(
  records: DailyAccuracyRecord[],
  cutoff: string = '09:00'
): void {
  const headers = [
    'delivery_date',
    'cutoff_time',
    'total_settlement_periods',
    'mae_mw',
    'forecast_bias_mw',
    'rmse_mw',
    'shortfall_frequency_pct',
    'shortfall_periods_count',
    'max_period_shortfall_mw',
  ];

  const rows = records.map((d) => [
    d.date,
    cutoff,
    d.total_periods,
    d.mae_mw,
    d.bias_mw,
    d.rmse_mw,
    `${d.shortfall_frequency_pct}%`,
    d.shortfall_periods_count,
    d.max_shortfall_mw,
  ]);

  const csvContent = [headers.join(','), ...rows.map((row) => row.join(','))].join('\r\n');
  downloadCsvFile(`wind_forecast_accuracy_30day_benchmark_jan2026.csv`, csvContent);
}

/**
 * Export Deep-Dive Failure Modes
 */
export function exportDeepDiveCsv(records: HourlyErrorRecord[], cutoff: string = '09:00'): void {
  const headers = [
    'hour_of_day',
    'time_window_london',
    'cutoff_time',
    'mae_mw',
    'signed_bias_mw',
    'p90_shortfall_mw',
    'is_peak_window',
    'operational_window',
  ];

  const rows = records.map((h) => [
    h.hour,
    `"${h.time_label}"`,
    cutoff,
    h.mae_mw,
    h.bias_mw,
    h.p90_shortfall_mw,
    h.is_peak_window ? 'Yes' : 'No',
    h.hour >= 17 && h.hour <= 20 ? 'Evening Peak (Critical)' : h.hour >= 6 && h.hour <= 12 ? 'Morning Ramp' : 'Baseline',
  ]);

  const csvContent = [headers.join(','), ...rows.map((row) => row.join(','))].join('\r\n');
  downloadCsvFile(`wind_forecast_diurnal_failure_modes_cutoff${cutoff.replace(':', '')}.csv`, csvContent);
}
