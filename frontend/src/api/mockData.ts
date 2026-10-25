import {
  AccuracySummaryResult,
  BufferCalibrationData,
  DailyAccuracyRecord,
  DayAheadResult,
  DayAheadVintagesResult,
  DistributionResult,
  HorizonDegradationRecord,
  HourlyErrorRecord,
  SettlementPeriodRecord,
} from './types';

// Generate 48 settlement periods for delivery day 16 Jan 2026
export function getMockDayAhead(decisionDate = '2026-01-15', cutoff = '09:00', confidence = 90): DayAheadResult {
  // Profiles modeled on actual 16 Jan 2026 UK day-ahead wind outturn
  // 48 periods (00:00 - 24:00, 30 min intervals)
  const baseForecast = [
    6800, 6650, 6400, 6100, 5700, 5200, 4600, 4000, // 00:00 - 04:00
    3500, 3250, 3150, 3120, 3110, 3200, 3500, 4100, // 04:00 - 08:00 (SP 13 min 3110 MW)
    4900, 5900, 7100, 8200, 8900, 9300, 9400, 9250, // 08:00 - 12:00 (Morning ramp)
    9050, 8950, 8900, 8920, 9100, 9400, 9800, 10300, // 12:00 - 16:00 (SP 28: 8920 MW)
    10900, 11500, 12100, 12500, 12750, 12820, 12850, 12600, // 16:00 - 20:00 (SP 39 max 12850 MW)
    12100, 11400, 10500, 9600, 8600, 7600, 6800, 6100, // 20:00 - 24:00
  ];

  // Actual generation curve with daytime deviations and peak evening shortfall
  const baseActual = [
    6880, 6760, 6530, 6240, 5810, 5280, 4690, 4090, // +80 to +90 surplus
    3600, 3350, 3260, 3220, 3210, 3310, 3620, 4230, // mild surplus
    5030, 6060, 7260, 8360, 9020, 9380, 9420, 9210, // ramp
    8930, 8800, 8735, 8480, 8660, 8960, 9420, 9980, // SP 28: 8480 (-440 shortfall)
    10560, 11120, 11650, 12040, 12210, 12140, 11710, 11820, // SP 39: 11710 (-1140 shortfall)
    11560, 11020, 10210, 9420, 8490, 7540, 6760, 6080,
  ];

  let bufferMw = 410;
  if (confidence === 80) bufferMw = 290;
  if (confidence === 90) bufferMw = 410;
  if (confidence === 95) bufferMw = 580;
  if (confidence === 99) bufferMw = 840;

  const records: SettlementPeriodRecord[] = [];
  let shortfallCount = 0;
  let surplusCount = 0;
  let absErrorSum = 0;
  let errorSum = 0;
  let sqErrorSum = 0;
  let worstShortfall = 0;
  let worstPeriod = 39;

  for (let i = 0; i < 48; i++) {
    const period = i + 1;
    const hour = Math.floor(i / 2);
    const minute = i % 2 === 0 ? '00' : '30';
    const endHour = i % 2 === 0 ? hour : (hour + 1) % 24;
    const endMinute = i % 2 === 0 ? '30' : '00';

    const startTime = `${String(hour).padStart(2, '0')}:${minute}`;
    const endTime = `${String(endHour).padStart(2, '0')}:${endMinute}`;

    const fc = baseForecast[i];
    const act = baseActual[i];
    const err = act - fc; // delta: act - fc (negative = shortfall)
    const absErr = Math.abs(err);
    const errPct = Number(((err / fc) * 100).toFixed(1));
    const isShortfall = err < 0;

    if (isShortfall) {
      shortfallCount++;
      if (err < worstShortfall) {
        worstShortfall = err;
        worstPeriod = period;
      }
    } else {
      surplusCount++;
    }

    absErrorSum += absErr;
    errorSum += (fc - act); // bias convention: forecast - actual
    sqErrorSum += err * err;

    records.push({
      period,
      start_time: startTime,
      end_time: endTime,
      forecast_mw: fc,
      forecast_publish_time: '2026-01-15T08:00:00Z',
      horizon_hours: 16 + (i * 0.5),
      actual_mw: act,
      error_mw: err,
      error_pct: errPct,
      is_shortfall: isShortfall,
      buffer_p90_mw: bufferMw,
    });
  }

  const expectedAvg = Math.round(baseForecast.reduce((a, b) => a + b, 0) / 48);
  const totalMwh = expectedAvg * 24;

  return {
    decision_date: decisionDate,
    delivery_date: '2026-01-16',
    cutoff_time: cutoff,
    selected_vintage_time: '2026-01-15T08:00:00Z',
    forecast_age_hours: 1.0,
    total_periods: 48,
    available_periods: 48,
    coverage_pct: 100.0,
    expected_avg_mw: expectedAvg,
    total_delivery_mwh: totalMwh,
    lowest_period: {
      period: 13,
      time: '06:30',
      forecast_mw: 3110,
      actual_mw: 3210,
    },
    highest_period: {
      period: 39,
      time: '19:30',
      forecast_mw: 12850,
      actual_mw: 11710,
    },
    buffer_recommended_mw: bufferMw,
    buffer_total_mwh: bufferMw * 24,
    summary_metrics: {
      mae_mw: Math.round(absErrorSum / 48),
      bias_mw: Math.round(errorSum / 48),
      rmse_mw: Math.round(Math.sqrt(sqErrorSum / 48)),
      worst_shortfall_period: worstPeriod,
      worst_shortfall_mw: worstShortfall,
      shortfall_periods_count: shortfallCount,
      surplus_periods_count: surplusCount,
    },
    records,
  };
}

// 30-Day Benchmark Summary
export const mockAccuracySummary: AccuracySummaryResult = {
  evaluation_window: {
    from_date: '2026-01-01',
    to_date: '2026-01-31',
    cutoff: '09:00',
    settlement_periods_count: 1488,
    days_count: 31,
  },
  mae_mw: 594,
  bias_mw: 136,
  rmse_mw: 742,
  wape_pct: 6.8,
  shortfall_frequency_pct: 27.8,
  mean_shortfall_mw: -428,
  max_shortfall_mw: -1420,
  max_shortfall_period_info: {
    date: '2026-01-18',
    period: 38,
    time: '19:00',
    shortfall_mw: -1420,
    event_label: 'Storm Gerrit Peak Ramp Outlier',
  },
  coverage_pct: 100.0,
  persistence_benchmark: {
    persistence_mae_mw: 964,
    skill_improvement_pct: 38.4,
  },
};

// 31 Days of January 2026 for Accuracy Table & Daily MAE chart
export const mockDailyAccuracy: DailyAccuracyRecord[] = [
  { date: '2026-01-01', mae_mw: 560, bias_mw: 90, rmse_mw: 690, shortfall_frequency_pct: 22.9, shortfall_periods_count: 11, max_shortfall_mw: -620, total_periods: 48 },
  { date: '2026-01-02', mae_mw: 500, bias_mw: 75, rmse_mw: 630, shortfall_frequency_pct: 20.8, shortfall_periods_count: 10, max_shortfall_mw: -540, total_periods: 48 },
  { date: '2026-01-03', mae_mw: 625, bias_mw: 145, rmse_mw: 780, shortfall_frequency_pct: 29.2, shortfall_periods_count: 14, max_shortfall_mw: -710, total_periods: 48 },
  { date: '2026-01-04', mae_mw: 540, bias_mw: 110, rmse_mw: 670, shortfall_frequency_pct: 25.0, shortfall_periods_count: 12, max_shortfall_mw: -590, total_periods: 48 },
  { date: '2026-01-05', mae_mw: 450, bias_mw: 60, rmse_mw: 580, shortfall_frequency_pct: 18.8, shortfall_periods_count: 9, max_shortfall_mw: -480, total_periods: 48 },
  { date: '2026-01-06', mae_mw: 400, bias_mw: 45, rmse_mw: 510, shortfall_frequency_pct: 16.7, shortfall_periods_count: 8, max_shortfall_mw: -420, total_periods: 48 },
  { date: '2026-01-07', mae_mw: 475, bias_mw: 85, rmse_mw: 600, shortfall_frequency_pct: 20.8, shortfall_periods_count: 10, max_shortfall_mw: -510, total_periods: 48 },
  { date: '2026-01-08', mae_mw: 675, bias_mw: 180, rmse_mw: 840, shortfall_frequency_pct: 33.3, shortfall_periods_count: 16, max_shortfall_mw: -820, total_periods: 48 },
  { date: '2026-01-09', mae_mw: 600, bias_mw: 130, rmse_mw: 750, shortfall_frequency_pct: 27.1, shortfall_periods_count: 13, max_shortfall_mw: -730, total_periods: 48 },
  { date: '2026-01-10', mae_mw: 425, bias_mw: 50, rmse_mw: 540, shortfall_frequency_pct: 18.8, shortfall_periods_count: 9, max_shortfall_mw: -460, total_periods: 48 },
  { date: '2026-01-11', mae_mw: 350, bias_mw: 20, rmse_mw: 440, shortfall_frequency_pct: 14.6, shortfall_periods_count: 7, max_shortfall_mw: -390, total_periods: 48 },
  { date: '2026-01-12', mae_mw: 550, bias_mw: 100, rmse_mw: 680, shortfall_frequency_pct: 25.0, shortfall_periods_count: 12, max_shortfall_mw: -630, total_periods: 48 },
  { date: '2026-01-13', mae_mw: 650, bias_mw: 160, rmse_mw: 810, shortfall_frequency_pct: 31.3, shortfall_periods_count: 15, max_shortfall_mw: -790, total_periods: 48 },
  { date: '2026-01-14', mae_mw: 590, bias_mw: 120, rmse_mw: 730, shortfall_frequency_pct: 27.1, shortfall_periods_count: 13, max_shortfall_mw: -690, total_periods: 48 },
  { date: '2026-01-15', mae_mw: 525, bias_mw: 95, rmse_mw: 650, shortfall_frequency_pct: 22.9, shortfall_periods_count: 11, max_shortfall_mw: -580, total_periods: 48 },
  { date: '2026-01-16', mae_mw: 482, bias_mw: 124, rmse_mw: 614, shortfall_frequency_pct: 25.0, shortfall_periods_count: 12, max_shortfall_mw: -1140, total_periods: 48 },
  { date: '2026-01-17', mae_mw: 750, bias_mw: 210, rmse_mw: 930, shortfall_frequency_pct: 37.5, shortfall_periods_count: 18, max_shortfall_mw: -960, total_periods: 48 },
  { date: '2026-01-18', mae_mw: 1124, bias_mw: -340, rmse_mw: 1420, shortfall_frequency_pct: 54.2, shortfall_periods_count: 26, max_shortfall_mw: -1420, total_periods: 48 }, // Storm Gerrit
  { date: '2026-01-19', mae_mw: 775, bias_mw: 110, rmse_mw: 960, shortfall_frequency_pct: 35.4, shortfall_periods_count: 17, max_shortfall_mw: -890, total_periods: 48 },
  { date: '2026-01-20', mae_mw: 575, bias_mw: 90, rmse_mw: 710, shortfall_frequency_pct: 25.0, shortfall_periods_count: 12, max_shortfall_mw: -640, total_periods: 48 },
  { date: '2026-01-21', mae_mw: 500, bias_mw: 80, rmse_mw: 620, shortfall_frequency_pct: 20.8, shortfall_periods_count: 10, max_shortfall_mw: -550, total_periods: 48 },
  { date: '2026-01-22', mae_mw: 625, bias_mw: 150, rmse_mw: 770, shortfall_frequency_pct: 29.2, shortfall_periods_count: 14, max_shortfall_mw: -720, total_periods: 48 },
  { date: '2026-01-23', mae_mw: 450, bias_mw: 40, rmse_mw: 560, shortfall_frequency_pct: 18.8, shortfall_periods_count: 9, max_shortfall_mw: -490, total_periods: 48 },
  { date: '2026-01-24', mae_mw: 375, bias_mw: 15, rmse_mw: 470, shortfall_frequency_pct: 14.6, shortfall_periods_count: 7, max_shortfall_mw: -410, total_periods: 48 },
  { date: '2026-01-25', mae_mw: 460, bias_mw: 60, rmse_mw: 570, shortfall_frequency_pct: 18.8, shortfall_periods_count: 9, max_shortfall_mw: -510, total_periods: 48 },
  { date: '2026-01-26', mae_mw: 550, bias_mw: 110, rmse_mw: 680, shortfall_frequency_pct: 25.0, shortfall_periods_count: 12, max_shortfall_mw: -620, total_periods: 48 },
  { date: '2026-01-27', mae_mw: 600, bias_mw: 135, rmse_mw: 740, shortfall_frequency_pct: 27.1, shortfall_periods_count: 13, max_shortfall_mw: -700, total_periods: 48 },
  { date: '2026-01-28', mae_mw: 440, bias_mw: 55, rmse_mw: 550, shortfall_frequency_pct: 18.8, shortfall_periods_count: 9, max_shortfall_mw: -480, total_periods: 48 },
  { date: '2026-01-29', mae_mw: 400, bias_mw: 35, rmse_mw: 500, shortfall_frequency_pct: 16.7, shortfall_periods_count: 8, max_shortfall_mw: -430, total_periods: 48 },
  { date: '2026-01-30', mae_mw: 475, bias_mw: 70, rmse_mw: 590, shortfall_frequency_pct: 20.8, shortfall_periods_count: 10, max_shortfall_mw: -520, total_periods: 48 },
  { date: '2026-01-31', mae_mw: 510, bias_mw: 85, rmse_mw: 630, shortfall_frequency_pct: 22.9, shortfall_periods_count: 11, max_shortfall_mw: -560, total_periods: 48 },
];

// Diurnal hourly error records (24 hours)
export const mockHourlyErrors: HourlyErrorRecord[] = [
  { hour: 0, time_label: '00:00', mae_mw: 390, bias_mw: 45, p90_shortfall_mw: -220, is_peak_window: false },
  { hour: 1, time_label: '01:00', mae_mw: 360, bias_mw: 55, p90_shortfall_mw: -200, is_peak_window: false },
  { hour: 2, time_label: '02:00', mae_mw: 340, bias_mw: 60, p90_shortfall_mw: -190, is_peak_window: false },
  { hour: 3, time_label: '03:00', mae_mw: 320, bias_mw: 50, p90_shortfall_mw: -180, is_peak_window: false },
  { hour: 4, time_label: '04:00', mae_mw: 365, bias_mw: 40, p90_shortfall_mw: -210, is_peak_window: false },
  { hour: 5, time_label: '05:00', mae_mw: 420, bias_mw: 35, p90_shortfall_mw: -260, is_peak_window: false },
  { hour: 6, time_label: '06:00', mae_mw: 520, bias_mw: -85, p90_shortfall_mw: -380, is_peak_window: false }, // Morning ramp
  { hour: 7, time_label: '07:00', mae_mw: 590, bias_mw: -130, p90_shortfall_mw: -460, is_peak_window: false },
  { hour: 8, time_label: '08:00', mae_mw: 560, bias_mw: -90, p90_shortfall_mw: -440, is_peak_window: false },
  { hour: 9, time_label: '09:00', mae_mw: 490, bias_mw: 10, p90_shortfall_mw: -340, is_peak_window: false },
  { hour: 10, time_label: '10:00', mae_mw: 440, bias_mw: 70, p90_shortfall_mw: -280, is_peak_window: false },
  { hour: 11, time_label: '11:00', mae_mw: 420, bias_mw: 85, p90_shortfall_mw: -260, is_peak_window: false },
  { hour: 12, time_label: '12:00', mae_mw: 430, bias_mw: 75, p90_shortfall_mw: -270, is_peak_window: false },
  { hour: 13, time_label: '13:00', mae_mw: 450, bias_mw: 60, p90_shortfall_mw: -290, is_peak_window: false },
  { hour: 14, time_label: '14:00', mae_mw: 470, bias_mw: 40, p90_shortfall_mw: -310, is_peak_window: false },
  { hour: 15, time_label: '15:00', mae_mw: 540, bias_mw: -20, p90_shortfall_mw: -390, is_peak_window: false },
  { hour: 16, time_label: '16:00', mae_mw: 640, bias_mw: -120, p90_shortfall_mw: -490, is_peak_window: true }, // Evening peak window
  { hour: 17, time_label: '17:00', mae_mw: 720, bias_mw: -210, p90_shortfall_mw: -620, is_peak_window: true },
  { hour: 18, time_label: '18:00', mae_mw: 810, bias_mw: -310, p90_shortfall_mw: -750, is_peak_window: true },
  { hour: 19, time_label: '19:00', mae_mw: 840, bias_mw: -340, p90_shortfall_mw: -780, is_peak_window: true }, // Peak drop
  { hour: 20, time_label: '20:00', mae_mw: 760, bias_mw: -220, p90_shortfall_mw: -660, is_peak_window: true },
  { hour: 21, time_label: '21:00', mae_mw: 610, bias_mw: -80, p90_shortfall_mw: -440, is_peak_window: false },
  { hour: 22, time_label: '22:00', mae_mw: 480, bias_mw: 20, p90_shortfall_mw: -310, is_peak_window: false },
  { hour: 23, time_label: '23:00', mae_mw: 420, bias_mw: 40, p90_shortfall_mw: -250, is_peak_window: false },
];

// Horizon degradation curve
export const mockHorizonCurve: HorizonDegradationRecord[] = [
  { horizon_hours: 1, mae_mw: 320, bias_mw: 25, records_count: 1488 },
  { horizon_hours: 6, mae_mw: 395, bias_mw: 48, records_count: 1488 },
  { horizon_hours: 12, mae_mw: 470, bias_mw: 78, records_count: 1488 },
  { horizon_hours: 18, mae_mw: 535, bias_mw: 104, records_count: 1488 },
  { horizon_hours: 24, mae_mw: 594, bias_mw: 136, records_count: 1488 }, // 09:00 Day-Ahead Cut-off baseline
  { horizon_hours: 36, mae_mw: 710, bias_mw: 185, records_count: 1488 },
  { horizon_hours: 48, mae_mw: 820, bias_mw: 240, records_count: 1488 },
];

// Error Distribution Histogram & Quantiles
export const mockDistribution: DistributionResult = {
  p5_mw: -880,
  p10_mw: -610,
  p25_mw: -220,
  p50_median_mw: 110,
  p75_mw: 440,
  p90_mw: 740,
  p95_mw: 980,
  bins: [
    { bin_center_mw: -1300, bin_min_mw: -1400, bin_max_mw: -1200, count: 8, is_shortfall_tail: true },
    { bin_center_mw: -1100, bin_min_mw: -1200, bin_max_mw: -1000, count: 18, is_shortfall_tail: true },
    { bin_center_mw: -900, bin_min_mw: -1000, bin_max_mw: -800, count: 35, is_shortfall_tail: true },
    { bin_center_mw: -700, bin_min_mw: -800, bin_max_mw: -600, count: 68, is_shortfall_tail: true },
    { bin_center_mw: -500, bin_min_mw: -600, bin_max_mw: -400, count: 112, is_shortfall_tail: true },
    { bin_center_mw: -300, bin_min_mw: -400, bin_max_mw: -200, count: 168, is_shortfall_tail: true },
    { bin_center_mw: -100, bin_min_mw: -200, bin_max_mw: 0, count: 224, is_shortfall_tail: false },
    { bin_center_mw: 100, bin_min_mw: 0, bin_max_mw: 200, count: 254, is_shortfall_tail: false },
    { bin_center_mw: 300, bin_min_mw: 200, bin_max_mw: 400, count: 215, is_shortfall_tail: false },
    { bin_center_mw: 500, bin_min_mw: 400, bin_max_mw: 600, count: 162, is_shortfall_tail: false },
    { bin_center_mw: 700, bin_min_mw: 600, bin_max_mw: 800, count: 115, is_shortfall_tail: false },
    { bin_center_mw: 900, bin_min_mw: 800, bin_max_mw: 1000, count: 64, is_shortfall_tail: false },
    { bin_center_mw: 1100, bin_min_mw: 1000, bin_max_mw: 1200, count: 32, is_shortfall_tail: false },
    { bin_center_mw: 1300, bin_min_mw: 1200, bin_max_mw: 1400, count: 13, is_shortfall_tail: false },
  ],
};

// Vintages for 16 Jan 2026 delivery
export const mockVintagesResult: DayAheadVintagesResult = {
  delivery_date: '2026-01-16',
  cutoff_time: '09:00',
  selected_vintage_publish_time: '2026-01-15T08:00:00Z',
  actuals: getMockDayAhead('2026-01-15', '09:00', 90).records.map(r => ({
    period: r.period,
    actual_mw: r.actual_mw || 0,
  })),
  vintages: [
    {
      vintage_id: 'v1',
      publish_time: '2026-01-14T17:00:00Z',
      label: 'D-2 17:00 (Early ECMWF)',
      is_selected_at_cutoff: false,
      is_post_cutoff: false,
      periods: getMockDayAhead('2026-01-15', '09:00', 90).records.map(r => ({
        period: r.period,
        forecast_mw: Math.round(r.forecast_mw * 1.08 + (r.period > 30 ? 600 : -200)),
      })),
    },
    {
      vintage_id: 'v2',
      publish_time: '2026-01-15T02:00:00Z',
      label: 'D-1 02:00 (Overnight run)',
      is_selected_at_cutoff: false,
      is_post_cutoff: false,
      periods: getMockDayAhead('2026-01-15', '09:00', 90).records.map(r => ({
        period: r.period,
        forecast_mw: Math.round(r.forecast_mw * 1.04 + (r.period > 35 ? 350 : -100)),
      })),
    },
    {
      vintage_id: 'v3',
      publish_time: '2026-01-15T05:00:00Z',
      label: 'D-1 05:00 (Early morning update)',
      is_selected_at_cutoff: false,
      is_post_cutoff: false,
      periods: getMockDayAhead('2026-01-15', '09:00', 90).records.map(r => ({
        period: r.period,
        forecast_mw: Math.round(r.forecast_mw * 1.02),
      })),
    },
    {
      vintage_id: 'v4',
      publish_time: '2026-01-15T08:00:00Z',
      label: 'D-1 08:00 (Locked at 09:00 Cut-off)',
      is_selected_at_cutoff: true,
      is_post_cutoff: false,
      periods: getMockDayAhead('2026-01-15', '09:00', 90).records.map(r => ({
        period: r.period,
        forecast_mw: r.forecast_mw,
      })),
    },
    {
      vintage_id: 'v5',
      publish_time: '2026-01-15T14:00:00Z',
      label: 'D-1 14:00 (Post-Cutoff / Excluded)',
      is_selected_at_cutoff: false,
      is_post_cutoff: true,
      periods: getMockDayAhead('2026-01-15', '09:00', 90).records.map(r => ({
        period: r.period,
        forecast_mw: Math.round(r.forecast_mw * 0.98 + 40),
      })),
    },
  ],
};

// Buffer calibration configurations
export const mockBufferCalibrations: Record<number, BufferCalibrationData> = {
  80: {
    confidence_pct: 80,
    baseline_buffer_mw: 290,
    morning_ramp_buffer_mw: 270,
    afternoon_trough_buffer_mw: 210,
    evening_peak_buffer_mw: 460,
    night_baseline_buffer_mw: 150,
    mitigation_effectiveness_pct: 82,
  },
  90: {
    confidence_pct: 90,
    baseline_buffer_mw: 410,
    morning_ramp_buffer_mw: 380,
    afternoon_trough_buffer_mw: 290,
    evening_peak_buffer_mw: 640,
    night_baseline_buffer_mw: 210,
    mitigation_effectiveness_pct: 92,
  },
  95: {
    confidence_pct: 95,
    baseline_buffer_mw: 580,
    morning_ramp_buffer_mw: 520,
    afternoon_trough_buffer_mw: 410,
    evening_peak_buffer_mw: 860,
    night_baseline_buffer_mw: 290,
    mitigation_effectiveness_pct: 97,
  },
  99: {
    confidence_pct: 99,
    baseline_buffer_mw: 840,
    morning_ramp_buffer_mw: 760,
    afternoon_trough_buffer_mw: 590,
    evening_peak_buffer_mw: 1220,
    night_baseline_buffer_mw: 410,
    mitigation_effectiveness_pct: 99.5,
  },
};
