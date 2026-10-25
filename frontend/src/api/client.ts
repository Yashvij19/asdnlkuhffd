import {
  AccuracySummaryResult,
  DailyAccuracyRecord,
  DayAheadResult,
  DayAheadVintagesResult,
  DistributionResult,
  HorizonDegradationRecord,
  HourlyErrorRecord,
} from './types';
import {
  getMockDayAhead,
  mockAccuracySummary,
  mockDailyAccuracy,
  mockDistribution,
  mockHorizonCurve,
  mockHourlyErrors,
  mockVintagesResult,
} from './mockData';

const BASE_URL = '/api/v1';

async function fetchWithFallback<T>(url: string, fallback: T): Promise<T> {
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 4000);
    const res = await fetch(url, { signal: controller.signal });
    clearTimeout(timeout);

    if (!res.ok) {
      console.warn(`API call returned ${res.status} for ${url}, using fallback.`);
      return fallback;
    }
    const data = await res.json();
    return data as T;
  } catch (err) {
    console.info(`API unreachable at ${url}, using offline fallback dataset.`);
    return fallback;
  }
}

export const api = {
  // 1. Day-Ahead Forecast at cutoff
  async getDayAhead(decisionDate = '2026-01-15', cutoff = '09:00', confidence = 90): Promise<DayAheadResult> {
    const url = `${BASE_URL}/day-ahead?decision_date=${decisionDate}&cutoff=${cutoff}`;
    const fallback = getMockDayAhead(decisionDate, cutoff, confidence);
    const data = await fetchWithFallback<any>(url, fallback);

    // If backend returns data, map its schema to our frontend interface
    const rawList = data?.points || data?.records;
    if (data && rawList && Array.isArray(rawList)) {
      return {
        ...fallback,
        ...data,
        buffer_recommended_mw: fallback.buffer_recommended_mw,
        buffer_total_mwh: fallback.buffer_total_mwh,
        summary_metrics: {
          mae_mw: Math.round(data.summary?.mae_mw ?? fallback.summary_metrics.mae_mw),
          bias_mw: Math.round(data.summary?.bias_mw ?? fallback.summary_metrics.bias_mw),
          rmse_mw: Math.round(data.summary?.rmse_mw ?? fallback.summary_metrics.rmse_mw),
          worst_shortfall_period: fallback.summary_metrics.worst_shortfall_period,
          worst_shortfall_mw: fallback.summary_metrics.worst_shortfall_mw,
          shortfall_periods_count: fallback.summary_metrics.shortfall_periods_count,
          surplus_periods_count: fallback.summary_metrics.surplus_periods_count,
        },
        records: rawList.map((r: any, idx: number) => {
          const startTimeStr = r.start_time
            ? new Date(r.start_time).toISOString().substring(11, 16)
            : fallback.records[idx]?.start_time;

          let fcMw = r.forecast_mw;
          if (fcMw == null) {
            // If hourly forecast is given, even periods carry forward the previous period's forecast
            fcMw = rawList[idx - 1]?.forecast_mw ?? fallback.records[idx]?.forecast_mw ?? 0;
          }

          const actMw = r.actual_mw ?? fallback.records[idx]?.actual_mw ?? null;
          const errMw = (actMw != null && fcMw != null) ? (actMw - fcMw) : (r.error_mw ?? null);
          const errPct = (actMw != null && fcMw && fcMw > 0) ? ((errMw! / fcMw) * 100) : null;

          return {
            period: r.settlement_period || r.period || (idx + 1),
            start_time: startTimeStr,
            end_time: fallback.records[idx]?.end_time || '',
            forecast_mw: Math.round(fcMw),
            forecast_publish_time: r.forecast_publish_time || '2026-01-15T08:00:00Z',
            horizon_hours: r.horizon_hours || (16 + idx * 0.5),
            actual_mw: actMw != null ? Math.round(actMw) : null,
            error_mw: errMw != null ? Math.round(errMw) : null,
            error_pct: errPct != null ? Number(errPct.toFixed(1)) : null,
            is_shortfall: (errMw != null && errMw < 0),
            buffer_p90_mw: fallback.buffer_recommended_mw,
          };
        }),
      };
    }
    return fallback;
  },

  // 2. Vintages Evolution
  async getDayAheadVintages(deliveryDate = '2026-01-16'): Promise<DayAheadVintagesResult> {
    const url = `${BASE_URL}/day-ahead/vintages?delivery_date=${deliveryDate}`;
    const res = await fetchWithFallback<any>(url, mockVintagesResult);
    if (res && (res.vintages || res.records)) {
      const rawVintages = res.vintages || res.records || [];
      return {
        delivery_date: res.delivery_date || deliveryDate,
        cutoff_time: res.cutoff_time || '09:00',
        selected_vintage_publish_time: res.selected_vintage_publish_time || '',
        vintages: rawVintages.map((v: any, vIdx: number) => ({
          vintage_id: v.vintage_id || v.publish_time_utc || `vintage-${vIdx}`,
          publish_time: v.publish_time || v.publish_time_utc || '',
          label: v.label || v.vintage_label || `Vintage ${vIdx + 1}`,
          is_selected_at_cutoff: v.is_selected_at_cutoff ?? (v.publish_time_utc === '2026-01-15T07:30:00Z'),
          is_post_cutoff: v.is_post_cutoff ?? (v.publish_time_utc > '2026-01-15T09:00:00Z'),
          periods: (v.points || v.periods || []).map((p: any, pIdx: number) => ({
            period: p.settlement_period || p.period || (pIdx + 1),
            forecast_mw: Number(p.forecast_mw) || 0,
          })),
        })),
        actuals: (res.actuals || []).map((a: any, aIdx: number) => ({
          period: a.settlement_period || a.period || (aIdx + 1),
          actual_mw: Number(a.actual_mw) || 0,
        })),
      };
    }
    return mockVintagesResult;
  },

  // 3. Accuracy Summary (30-day KPI benchmark)
  async getAccuracySummary(from = '2026-01-01', to = '2026-01-31', cutoff = '09:00'): Promise<AccuracySummaryResult> {
    const url = `${BASE_URL}/accuracy/summary?from=${from}&to=${to}&cutoff=${cutoff}`;
    const res = await fetchWithFallback<any>(url, mockAccuracySummary);
    if (res && res.metrics) {
      return {
        ...mockAccuracySummary,
        mae_mw: Math.round(res.metrics.mae_mw ?? 594),
        bias_mw: Math.round(res.metrics.bias_mw ?? 136),
        rmse_mw: Math.round(res.metrics.rmse_mw ?? 742),
        wape_pct: Number((res.metrics.wape_pct ?? 6.8).toFixed(1)),
        shortfall_frequency_pct: Number((res.metrics.shortfall_frequency_pct ?? 27.8).toFixed(1)),
        mean_shortfall_mw: Math.round(res.metrics.mean_shortfall_mw ?? -428),
        max_shortfall_mw: Math.round(res.metrics.max_shortfall_mw ?? -1420),
        coverage_pct: Number((res.metrics.coverage_pct ?? 100).toFixed(1)),
      };
    }
    return mockAccuracySummary;
  },

  // 4. Daily Accuracy Breakdown
  async getDailyAccuracy(from = '2026-01-01', to = '2026-01-31', cutoff = '09:00'): Promise<DailyAccuracyRecord[]> {
    const url = `${BASE_URL}/accuracy/by-day?from=${from}&to=${to}&cutoff=${cutoff}`;
    const res = await fetchWithFallback<any>(url, null);
    const list = res?.items || res?.breakdown;
    if (list && Array.isArray(list)) {
      return list.map((b: any) => ({
        date: b.dimension_key || b.bucket_key || b.date,
        mae_mw: Math.round(b.mae_mw ?? 500),
        bias_mw: Math.round(b.bias_mw ?? 50),
        rmse_mw: Math.round(b.rmse_mw ?? 600),
        shortfall_frequency_pct: Number((b.shortfall_frequency_pct ?? b.shortfall_pct ?? 25).toFixed(1)),
        shortfall_periods_count: b.shortfall_periods ?? Math.round(((b.shortfall_frequency_pct ?? 25) / 100) * (b.count ?? 48)),
        max_shortfall_mw: Math.round(b.max_shortfall_mw ?? -600),
        total_periods: b.count ?? 48,
      }));
    }
    return mockDailyAccuracy;
  },

  // 5. Hourly Error Profiles (Diurnal)
  async getHourlyErrors(from = '2026-01-01', to = '2026-01-31', cutoff = '09:00'): Promise<HourlyErrorRecord[]> {
    const url = `${BASE_URL}/accuracy/by-hour?from=${from}&to=${to}&cutoff=${cutoff}`;
    const res = await fetchWithFallback<any>(url, null);
    const list = res?.items || res?.breakdown;
    if (list && Array.isArray(list)) {
      return list.map((h: any, idx: number) => {
        const hourNum = !isNaN(parseInt(h.dimension_key, 10)) ? parseInt(h.dimension_key, 10) : idx;
        return {
          hour: hourNum,
          time_label: h.dimension_label || h.bucket_label || `${String(hourNum).padStart(2, '0')}:00`,
          mae_mw: Math.round(h.mae_mw ?? mockHourlyErrors[idx]?.mae_mw ?? 450),
          bias_mw: Math.round(h.bias_mw ?? mockHourlyErrors[idx]?.bias_mw ?? 0),
          p90_shortfall_mw: Math.round(h.max_shortfall_mw ?? mockHourlyErrors[idx]?.p90_shortfall_mw ?? -300),
          is_peak_window: hourNum >= 16 && hourNum <= 20,
        };
      });
    }
    return mockHourlyErrors;
  },

  // 6. Horizon Degradation Curve
  async getHorizonCurve(): Promise<HorizonDegradationRecord[]> {
    const url = `${BASE_URL}/accuracy/by-horizon`;
    const res = await fetchWithFallback<any>(url, null);
    const list = res?.items || res?.breakdown;
    if (list && Array.isArray(list)) {
      return list.map((h: any, idx: number) => {
        const hKey = String(h.dimension_key || h.bucket_key || '');
        const match = hKey.match(/\d+/);
        const hHours = match ? parseInt(match[0], 10) : (idx + 1) * 6;
        return {
          horizon_hours: hHours || (idx + 1) * 6,
          mae_mw: Math.round(h.mae_mw ?? 500),
          bias_mw: Math.round(h.bias_mw ?? 50),
          records_count: h.count ?? 1488,
        };
      });
    }
    return mockHorizonCurve;
  },

  // 7. Error Distribution & Quantiles
  async getDistribution(from = '2026-01-01', to = '2026-01-31', cutoff = '09:00'): Promise<DistributionResult> {
    const url = `${BASE_URL}/accuracy/distribution?from=${from}&to=${to}&cutoff=${cutoff}`;
    const res = await fetchWithFallback<any>(url, null);
    if (res && res.bins && res.quantiles) {
      return {
        p5_mw: Math.round(res.quantiles.p5 ?? -880),
        p10_mw: Math.round(res.quantiles.p10 ?? -610),
        p25_mw: Math.round(res.quantiles.p25 ?? -220),
        p50_median_mw: Math.round(res.quantiles.p50 ?? 110),
        p75_mw: Math.round(res.quantiles.p75 ?? 440),
        p90_mw: Math.round(res.quantiles.p90 ?? 740),
        p95_mw: Math.round(res.quantiles.p95 ?? 980),
        bins: res.bins.map((b: any) => ({
          bin_center_mw: Math.round(b.bin_center ?? (b.bin_start + b.bin_end) / 2),
          bin_min_mw: Math.round(b.bin_start),
          bin_max_mw: Math.round(b.bin_end),
          count: b.count,
          is_shortfall_tail: b.bin_end <= 0,
        })),
      };
    }
    return mockDistribution;
  },

  // 8. CSV Export trigger
  exportCsvUrl(decisionDate = '2026-01-15', cutoff = '09:00'): string {
    return `${BASE_URL}/export/day-ahead.csv?decision_date=${decisionDate}&cutoff=${cutoff}`;
  },
};
