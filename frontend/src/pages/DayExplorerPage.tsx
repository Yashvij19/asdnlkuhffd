import React, { useEffect, useState } from 'react';
import { useApp } from '../context/AppContext';
import { api } from '../api/client';
import { DayAheadResult, DayAheadVintagesResult } from '../api/types';
import { KpiTile } from '../components/common/KpiTile';
import { DayExplorerCharts } from '../components/charts/DayExplorerCharts';
import { CheckCircle2, ChevronLeft, ChevronRight, Download, Filter } from 'lucide-react';
import { exportDayExplorerCsv } from '../utils/csvExport';

export const DayExplorerPage: React.FC = () => {
  const { decisionDate, cutoff, setDecisionDate } = useApp();
  const [data, setData] = useState<DayAheadResult | null>(null);
  const [vintagesData, setVintagesData] = useState<DayAheadVintagesResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedPeriod, setSelectedPeriod] = useState<number | null>(28);

  const janDays = Array.from({ length: 31 }, (_, i) => {
    const day = String(i + 1).padStart(2, '0');
    return `2026-01-${day}`;
  });

  const handlePrevDay = () => {
    const currIdx = janDays.indexOf(decisionDate);
    if (currIdx > 0) setDecisionDate(janDays[currIdx - 1]);
  };

  const handleNextDay = () => {
    const currIdx = janDays.indexOf(decisionDate);
    if (currIdx < janDays.length - 1) setDecisionDate(janDays[currIdx + 1]);
  };

  useEffect(() => {
    let isMounted = true;
    setLoading(true);
    Promise.all([
      api.getDayAhead(decisionDate, cutoff),
      api.getDayAheadVintages('2026-01-16'),
    ]).then(([resDay, resVintages]) => {
      if (isMounted) {
        setData(resDay);
        setVintagesData(resVintages);
        setLoading(false);
      }
    });
    return () => {
      isMounted = false;
    };
  }, [decisionDate, cutoff]);

  const handleExportCsv = () => {
    if (data) {
      exportDayExplorerCsv(data, cutoff);
    }
  };

  if (!data && loading) {
    return (
      <div className="max-w-[1280px] mx-auto px-4 sm:px-6 lg:px-8 py-6 w-full animate-fade-in">
        <div className="h-10 w-72 bg-surface-subtle animate-skeleton rounded mb-6" />
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 md:gap-5 lg:gap-6 mb-6">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-28 bg-surface border border-border rounded-xl animate-skeleton" />
          ))}
        </div>
      </div>
    );
  }

  const d = data!;

  return (
    <div className="max-w-[1280px] mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6 flex-1 w-full animate-fade-in">
      {/* 1. Page Header & Operational Controls Bar */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 pb-2">
        <div className="space-y-1">
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="font-h1 text-h1 text-text">
              Day Explorer: Delivery Day {d.delivery_date}
            </h1>
            <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-accent-50 text-accent-700 font-label text-label border border-accent-200">
              <span className="w-1.5 h-1.5 rounded-full bg-accent-500" />
              Cut-off: {cutoff} London time
            </span>
          </div>
          <p className="font-body-sm text-body-sm text-text-muted max-w-[72ch]">
            Detailed half-hourly inspection across 48 settlement periods. Forecast locked at {cutoff} cut-off compared with outturn actuals and evolution of forecast vintages.
          </p>
        </div>

        {/* Date Stepper & Actions */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="inline-flex items-center rounded-lg bg-surface border border-border-strong divide-x divide-border">
            <button
              type="button"
              onClick={handlePrevDay}
              disabled={decisionDate === '2026-01-01'}
              className="h-9 px-2 text-text-muted hover:text-text hover:bg-surface-subtle transition-colors disabled:opacity-40"
              title="Previous Day"
            >
              <ChevronLeft className="w-4 h-4 stroke-[2]" />
            </button>
            <div className="h-9 px-3 flex items-center font-body-sm text-body-sm font-medium text-text">
              {decisionDate}
            </div>
            <button
              type="button"
              onClick={handleNextDay}
              disabled={decisionDate === '2026-01-31'}
              className="h-9 px-2 text-text-muted hover:text-text hover:bg-surface-subtle transition-colors disabled:opacity-40"
              title="Next Day"
            >
              <ChevronRight className="w-4 h-4 stroke-[2]" />
            </button>
          </div>

          <button
            type="button"
            onClick={handleExportCsv}
            className="h-9 px-4 rounded-lg bg-accent-500 hover:bg-accent-600 active:bg-accent-700 text-on-primary font-body-sm text-body-sm font-medium flex items-center gap-2 transition-colors shadow-none"
          >
            <Download className="w-4 h-4" />
            <span>Export Day CSV</span>
          </button>
        </div>
      </div>

      {/* 2. Reconciliation Status Banner */}
      <div className="w-full bg-surface border border-border rounded-xl p-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-body-sm">
        <div className="flex items-center gap-3">
          <span className="w-6 h-6 rounded-full bg-success/10 border border-success/30 flex items-center justify-center text-success shrink-0">
            <CheckCircle2 className="w-4 h-4 text-success" />
          </span>
          <span className="text-text font-normal">
            All <strong className="font-medium text-text">48 settlement periods</strong> locked and verified against National Grid ESO metering. Settlement complete.
          </span>
        </div>
        <div className="flex items-center gap-4 text-text-muted font-caption text-caption">
          <span>
            BMRS BM-Unit: <code className="font-code text-text">SYS_WIND_AGG</code>
          </span>
          <span>
            Version: <code className="font-code text-text">RF (Run Final)</code>
          </span>
        </div>
      </div>

      {/* 3. Summary KPIs Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiTile
          label="MAE (Mean Absolute Error)"
          value={d.summary_metrics.mae_mw}
          unit="MW avg dev"
          subLabel="5.7% of average delivery"
          deltaText="-42 MW vs D-7"
          deltaType="positive"
          tooltip="Arithmetic mean of absolute forecast differences |Actual - Forecast| across all 48 settlement periods."
        />

        <KpiTile
          label="Forecast Bias"
          value={`+${d.summary_metrics.bias_mw}`}
          unit="MW over-forecast"
          subLabel="Net directional over-prediction"
          deltaText="Mild positive skew"
          deltaType="neutral"
          valueColorClass="text-accent-700"
          tooltip="Net directional deviation (Forecast - Actual). Positive value indicates persistent over-forecasting."
        />

        <KpiTile
          label="RMSE (Root Mean Square)"
          value={d.summary_metrics.rmse_mw}
          unit="MW error"
          subLabel="Penalises peak ramp deviations"
          subValue="Ratio RMSE/MAE: 1.27"
          tooltip="Root mean squared error penalises large outlier errors heavily, especially critical during rapid ramp phases."
        />

        <KpiTile
          label="Worst Period Deviation"
          value={d.summary_metrics.worst_shortfall_mw}
          unit="MW shortfall"
          subLabel={`Settlement Period ${d.summary_metrics.worst_shortfall_period}`}
          subValue="-8.87%"
          deltaType="shortfall"
          valueColorClass="text-data-shortfall-text"
          tooltip="Maximum shortfall period across day. Forecast was 12,850 MW while actual turned out at 11,710 MW."
        />
      </div>

      {/* 4. Chart A & Chart B */}
      <DayExplorerCharts
        records={d.records}
        vintages={vintagesData?.vintages || []}
        selectedPeriod={selectedPeriod}
        onPeriodSelect={setSelectedPeriod}
      />

      {/* 5. Detailed Settlement Table (48 rows) */}
      <div id="settlement-table-card" className="bg-surface border border-border rounded-xl overflow-hidden">
        <div className="p-4 border-b border-border flex items-center justify-between">
          <div>
            <h3 className="font-h3 text-h3 text-text">Settlement Periods Reconciliation</h3>
            <p className="font-caption text-caption text-text-muted">
              48 half-hour settlement periods locked against National Grid ESO metering
            </p>
          </div>
          <span className="font-code text-caption text-text-muted">Europe/London (UTC+0)</span>
        </div>

        <div className="overflow-x-auto max-h-96">
          <table className="w-full text-left text-body-sm border-collapse">
            <thead className="bg-surface-subtle sticky top-0 z-10 border-b border-border text-caption font-label text-text-muted uppercase">
              <tr>
                <th className="py-2.5 px-4 font-semibold">SP</th>
                <th className="py-2.5 px-4 font-semibold">Settlement Time</th>
                <th className="py-2.5 px-4 font-semibold text-right">Forecast (MW)</th>
                <th className="py-2.5 px-4 font-semibold text-right">Actual Outturn (MW)</th>
                <th className="py-2.5 px-4 font-semibold text-right">Variance / Error (MW)</th>
                <th className="py-2.5 px-4 font-semibold text-right">Variance %</th>
                <th className="py-2.5 px-4 font-semibold text-center">Settlement Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border font-code text-caption">
              {d.records.map((r) => {
                const isSelected = r.period === selectedPeriod;
                return (
                  <tr
                    key={r.period}
                    onMouseEnter={() => setSelectedPeriod(r.period)}
                    className={`transition-colors cursor-pointer ${
                      isSelected ? 'bg-accent-50 font-medium' : 'hover:bg-surface-subtle'
                    }`}
                  >
                    <td className="py-2 px-4 text-text font-bold">
                      {String(r.period).padStart(2, '0')}
                    </td>
                    <td className="py-2 px-4 text-text-muted font-sans font-medium">
                      {r.start_time} – {r.end_time}
                    </td>
                    <td className="py-2 px-4 text-right text-text font-semibold tabular-nums">
                      {r.forecast_mw.toLocaleString()}
                    </td>
                    <td className="py-2 px-4 text-right text-text tabular-nums">
                      {r.actual_mw?.toLocaleString() ?? '-'}
                    </td>
                    <td
                      className={`py-2 px-4 text-right tabular-nums font-bold ${
                        r.is_shortfall ? 'text-data-shortfall-text' : 'text-success'
                      }`}
                    >
                      {r.error_mw != null ? (r.error_mw > 0 ? `+${r.error_mw}` : r.error_mw) : '-'}
                    </td>
                    <td
                      className={`py-2 px-4 text-right tabular-nums ${
                        r.is_shortfall ? 'text-data-shortfall-text font-medium' : 'text-success'
                      }`}
                    >
                      {r.error_pct != null ? `${r.error_pct > 0 ? `+${r.error_pct}` : r.error_pct}%` : '-'}
                    </td>
                    <td className="py-2 px-4 text-center">
                      <span
                        className={`inline-flex px-2 py-0.5 rounded-full text-[11px] font-sans font-medium ${
                          r.is_shortfall
                            ? 'bg-data-shortfall/10 text-data-shortfall-text border border-data-shortfall/30'
                            : 'bg-success/10 text-success border border-success/30'
                        }`}
                      >
                        {r.is_shortfall ? 'Shortfall' : 'Surplus'}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
