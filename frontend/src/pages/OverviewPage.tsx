import React, { useEffect, useState } from 'react';
import { NavLink } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import { api } from '../api/client';
import { DayAheadResult } from '../api/types';
import { GlobalControls } from '../components/common/GlobalControls';
import { KpiTile } from '../components/common/KpiTile';
import { TimeSeriesChart } from '../components/charts/TimeSeriesChart';
import { InsightCallout } from '../components/common/InsightCallout';
import { ArrowRight, Download, ShieldAlert } from 'lucide-react';
import { exportDecisionBriefCsv } from '../utils/csvExport';

export const OverviewPage: React.FC = () => {
  const { decisionDate, cutoff, confidence, showActuals } = useApp();
  const [data, setData] = useState<DayAheadResult | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;
    setLoading(true);
    api.getDayAhead(decisionDate, cutoff, confidence).then((res) => {
      if (isMounted) {
        setData(res);
        setLoading(false);
      }
    });
    return () => {
      isMounted = false;
    };
  }, [decisionDate, cutoff, confidence]);

  const handleExportCsv = () => {
    if (data) {
      exportDecisionBriefCsv(data, cutoff);
    }
  };

  if (!data && loading) {
    return (
      <div className="max-w-[1280px] mx-auto px-4 sm:px-6 lg:px-8 py-6 w-full animate-fade-in">
        <div className="h-8 w-64 bg-surface-subtle animate-skeleton rounded mb-6" />
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4 md:gap-5 lg:gap-6 mb-6">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-28 bg-surface border border-border rounded-xl animate-skeleton" />
          ))}
        </div>
      </div>
    );
  }

  const d = data!;

  return (
    <div className="max-w-[1280px] mx-auto px-4 sm:px-6 lg:px-8 py-6 flex-1 w-full animate-fade-in">
      <div className="flex flex-col w-full">
        {/* Controls Bar & Parameters */}
        <GlobalControls showActualsToggle={true} showConfidenceSegment={true} />

        {/* Page Header Title & Subtitle */}
        <header className="mb-6">
          <div className="flex items-baseline gap-3">
            <span className="font-code text-caption text-accent-600 bg-accent-50 px-2 py-0.5 rounded uppercase font-medium tracking-wide">
              BMRS Locked Vintage
            </span>
            <span className="font-caption text-caption text-text-muted">
              Ingested: {decisionDate}, 09:02 UTC
            </span>
          </div>
          <h1 className="font-h1 text-h1 text-text tracking-tight mt-1">
            Decision brief: delivery day {d.delivery_date}
          </h1>
          <p className="font-body text-body text-text-muted max-w-4xl mt-1">
            National wind generation forecast locked at {cutoff} cut-off compared against clearing demand and empirical shortfall risk.
          </p>
        </header>

        {/* Bento Grid Container (6 columns on tablet, 12 columns on desktop xl) */}
        <div className="grid grid-cols-1 md:grid-cols-6 xl:grid-cols-12 gap-4 md:gap-5 lg:gap-6">
          {/* ROW 1: 4 KPI Cards (2x2 on tablet, 1x4 on desktop xl) */}
          <div className="col-span-1 md:col-span-3 xl:col-span-3">
            <KpiTile
              label="Expected average wind"
              value={d.expected_avg_mw.toLocaleString()}
              unit="MW"
              subLabel="Total day delivery"
              subValue={`${d.total_delivery_mwh.toLocaleString()} MWh`}
              tooltip="Mean predicted power generation across 48 settlement periods"
            />
          </div>

          <div className="col-span-1 md:col-span-3 xl:col-span-3">
            <KpiTile
              label="Lowest generation period"
              value={d.lowest_period.forecast_mw.toLocaleString()}
              unit="MW"
              subLabel={`Settlement period ${d.lowest_period.period}`}
              subValue={`${d.lowest_period.time} London`}
              tooltip="Minimum expected output period"
            />
          </div>

          <div className="col-span-1 md:col-span-3 xl:col-span-3">
            <KpiTile
              label="Highest evening peak"
              value={d.highest_period.forecast_mw.toLocaleString()}
              unit="MW"
              subLabel={`Settlement period ${d.highest_period.period}`}
              subValue={`${d.highest_period.time} London`}
              tooltip="Maximum expected peak generation"
            />
          </div>

          <div className="col-span-1 md:col-span-3 xl:col-span-3">
            <KpiTile
              label="Forecast age at cut-off"
              value={d.forecast_age_hours.toFixed(1)}
              unit="h before cut-off"
              subLabel="Vintage published"
              subValue="08:00 London"
              tooltip="Time elapsed between publication and trade cut-off"
            />
          </div>

          {/* ROW 2 & 3: Main Time Series Chart (Full width on tablet, 8 cols on desktop xl) */}
          <div className="col-span-1 md:col-span-6 xl:col-span-8 xl:row-span-2">
            <TimeSeriesChart
              records={d.records}
              showActuals={showActuals}
              onExportCsv={handleExportCsv}
              confidence={confidence}
            />
          </div>

          {/* ROW 2: Risk-Adjusted Wind KPI Card (Full width on tablet, 4 cols on desktop xl) */}
          <div className="col-span-1 md:col-span-6 xl:col-span-4 bg-surface border border-border rounded-xl p-5 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between">
                <span className="font-label text-label text-text-muted uppercase tracking-wider">
                  Operational Hedge
                </span>
                <span className="text-text-muted text-xs cursor-help" title="Procurement volume required to protect system balance under target confidence">
                  ⓘ
                </span>
              </div>
              <div className="mt-2">
                <h3 className="font-h3 text-h3 text-text">Recommended procurement buffer</h3>
                <p className="font-caption text-caption text-text-muted mt-0.5">
                  Calculated at {confidence}% empirical shortfall guarantee
                </p>
              </div>

              <div className="my-4">
                <div className="flex items-baseline gap-2">
                  <span className="font-kpi-value text-kpi-value text-text font-semibold tabular-nums">
                    {d.buffer_recommended_mw.toLocaleString()}
                  </span>
                  <span className="font-kpi-unit text-kpi-unit text-text-muted font-medium">
                    MW safety margin
                  </span>
                </div>
                <div className="mt-2 text-body-sm font-body-sm text-text-muted leading-relaxed">
                  Hold back{' '}
                  <strong className="text-text tabular-nums">{d.buffer_recommended_mw} MW</strong> average (
                  <span className="tabular-nums font-code text-caption text-text">
                    {d.buffer_total_mwh.toLocaleString()} MWh
                  </span>{' '}
                  total) to cover forecast downside during daytime imbalance windows.
                </div>
              </div>
            </div>

            <div>
              {/* Status Alert Pill */}
              <div className="flex items-center gap-2 p-2.5 rounded-lg bg-[#C2571A]/10 border border-[#C2571A]/30">
                <ShieldAlert className="w-4 h-4 text-data-shortfall shrink-0" />
                <span className="font-label text-label text-data-shortfall-text font-medium">
                  Shortfall risk moderate · Peak ramp exposure
                </span>
              </div>
            </div>
          </div>

          {/* ROW 3 (RIGHT 4 COLS): Accuracy Last 30 Days Card */}
          <div className="col-span-1 md:col-span-6 lg:col-span-4 bg-surface border border-border rounded-xl p-5 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between pb-2 border-b border-border">
                <h3 className="font-h4 text-h4 text-text">30-day forecast accuracy</h3>
                <span className="font-code text-caption text-text-muted">{cutoff} cut-off</span>
              </div>

              <div className="mt-3 divide-y divide-border">
                {/* MAE */}
                <div className="py-2.5 flex items-center justify-between">
                  <div>
                    <div className="font-body-sm text-body-sm text-text font-medium">
                      Mean Absolute Error (MAE)
                    </div>
                    <div className="font-caption text-caption text-text-muted">
                      System average absolute dev
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="font-code text-body-sm font-semibold text-text tabular-nums">
                      612 MW
                    </div>
                    <div className="font-caption text-caption text-text-muted tabular-nums">
                      7.3% capacity
                    </div>
                  </div>
                </div>

                {/* Bias */}
                <div className="py-2.5 flex items-center justify-between">
                  <div>
                    <div className="font-body-sm text-body-sm text-text font-medium">
                      Forecast Bias
                    </div>
                    <div className="font-caption text-caption text-text-muted">
                      Directional net tendency
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="font-code text-body-sm font-semibold text-data-shortfall-text tabular-nums">
                      +148 MW
                    </div>
                    <div className="font-caption text-caption text-text-muted">
                      Over-forecast tendency
                    </div>
                  </div>
                </div>

                {/* Shortfall Frequency */}
                <div className="py-2.5 flex items-center justify-between">
                  <div>
                    <div className="font-body-sm text-body-sm text-text font-medium">
                      Shortfall Frequency
                    </div>
                    <div className="font-caption text-caption text-text-muted">
                      Actual &lt; Forecast - 200MW
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="font-code text-body-sm font-semibold text-text tabular-nums">
                      28.4%
                    </div>
                    <div className="font-caption text-caption text-text-muted tabular-nums">
                      of settlement periods
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div className="pt-3 border-t border-border mt-1">
              <NavLink
                to="/accuracy"
                className="inline-flex items-center gap-1.5 font-label text-label text-accent-500 hover:text-accent-700 font-medium transition-colors"
              >
                <span>Open Accuracy Dashboard</span>
                <ArrowRight className="w-4 h-4" />
              </NavLink>
            </div>
          </div>

          {/* ROW 4: Decision Insights (3 Callouts: 4 cols each on desktop xl, 2 cols each on tablet) */}
          <div className="col-span-1 md:col-span-2 xl:col-span-4">
            <InsightCallout
              type="accent"
              title="Steep morning ramp risk"
              body={
                <>
                  Generation triples between 06:30 (<span className="font-code text-text font-medium tabular-nums">3,110 MW</span>) and 11:30 (<span className="font-code text-text font-medium tabular-nums">9,400 MW</span>). Historical forecast timing errors have averaged ±45 min in this morning ramp window.
                </>
              }
              footerLabel="Timing risk window:"
              footerValue="06:30 – 11:30"
            />
          </div>

          <div className="col-span-1 md:col-span-2 xl:col-span-4">
            <InsightCallout
              type="shortfall"
              title="Evening peak shortfall exposure"
              body={
                <>
                  Peak period 37–41 (18:30–20:30) carries the highest shortfall probability (<span className="font-code text-data-shortfall-text font-medium tabular-nums">34%</span>). Consider applying the full P90 buffer of 520 MW during evening peak demand.
                </>
              }
              footerLabel="High probability period:"
              footerValue="SP 37–41 (18:30–20:30)"
            />
          </div>

          <div className="col-span-1 md:col-span-2 xl:col-span-4">
            <InsightCallout
              type="success"
              title="Model consensus high"
              body={
                <>
                  Elexon BMRS day-ahead and ECMWF ensemble differ by &lt;3.2% across daytime settlement periods. Forecast confidence rating: <strong className="text-text font-medium">High</strong> across offshore and Scottish hubs.
                </>
              }
              footerLabel="Ensemble variance:"
              footerValue="< 3.2% spread"
            />
          </div>

          {/* ROW 5: Bottom Navigation & Decision Export Action Bar */}
          <div className="col-span-1 md:col-span-6 lg:col-span-12 flex flex-col sm:flex-row items-center justify-between gap-4 py-4 px-5 bg-surface border border-border rounded-xl">
            <div className="flex items-center gap-3 text-caption font-caption text-text-muted">
              <span className="w-2 h-2 rounded-full bg-accent-500 animate-pulse" />
              <span>
                Next forecast update scheduled at <strong>13:00 UTC</strong> · Gate Closure SP 25 at 11:00 UTC
              </span>
            </div>

            <div className="flex items-center gap-3 w-full sm:w-auto justify-end">
              <NavLink
                to="/day"
                className="h-9 px-4 inline-flex items-center justify-center font-body-sm text-body-sm font-medium bg-surface border border-border-strong text-text rounded-lg hover:bg-surface-subtle transition-colors"
              >
                View in Day Explorer
              </NavLink>

              <button
                type="button"
                onClick={handleExportCsv}
                className="h-9 px-4 inline-flex items-center justify-center gap-2 font-body-sm text-body-sm font-medium bg-accent-500 text-on-primary rounded-lg hover:bg-accent-600 active:bg-accent-700 transition-colors shadow-none"
              >
                <Download className="w-4 h-4" />
                <span>Export Decision Brief CSV</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
