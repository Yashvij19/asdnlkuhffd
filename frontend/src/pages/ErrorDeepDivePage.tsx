import React, { useEffect, useState } from 'react';
import { useApp } from '../context/AppContext';
import { api } from '../api/client';
import {
  DistributionResult,
  HorizonDegradationRecord,
  HourlyErrorRecord,
} from '../api/types';
import { mockBufferCalibrations } from '../api/mockData';
import {
  DistributionHistogram,
  HorizonDegradationChart,
  HourlyErrorChart,
} from '../components/charts/AccuracyCharts';
import { InsightCallout } from '../components/common/InsightCallout';
import { Download, ShieldCheck, Clock, Calendar, Layers, Activity, TrendingUp, BarChart2 } from 'lucide-react';
import { exportDeepDiveCsv } from '../utils/csvExport';

export const ErrorDeepDivePage: React.FC = () => {
  const { cutoff, confidence, setConfidence } = useApp();
  const [activeTab, setActiveTab] = useState<
    'all' | 'hour' | 'horizon' | 'level' | 'distribution' | 'buffer'
  >('all');
  const [hourlyErrors, setHourlyErrors] = useState<HourlyErrorRecord[]>([]);
  const [horizonCurve, setHorizonCurve] = useState<HorizonDegradationRecord[]>([]);
  const [distribution, setDistribution] = useState<DistributionResult | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;
    setLoading(true);
    Promise.all([
      api.getHourlyErrors('2026-01-01', '2026-01-31', cutoff),
      api.getHorizonCurve(),
      api.getDistribution('2026-01-01', '2026-01-31', cutoff),
    ]).then(([resHourly, resHorizon, resDist]) => {
      if (isMounted) {
        setHourlyErrors(resHourly);
        setHorizonCurve(resHorizon);
        setDistribution(resDist);
        setLoading(false);
      }
    });
    return () => {
      isMounted = false;
    };
  }, [cutoff]);

  const bufferConfig = mockBufferCalibrations[confidence] || mockBufferCalibrations[90];

  const handleExportCsv = () => {
    exportDeepDiveCsv(hourlyErrors, cutoff);
  };

  // Generation level breakdown data
  const generationLevels = [
    {
      range: '< 4,000 MW',
      label: 'Low Generation / Calm Anticyclone',
      mae_mw: 280,
      bias_mw: 45,
      periods_count: 320,
      risk_level: 'Low',
      risk_color: 'text-success',
      shortfall_pct: 12.5,
    },
    {
      range: '4,000 – 8,000 MW',
      label: 'Moderate Generation / Stable Wind',
      mae_mw: 490,
      bias_mw: 110,
      periods_count: 480,
      risk_level: 'Moderate',
      risk_color: 'text-accent-600',
      shortfall_pct: 22.8,
    },
    {
      range: '8,000 – 12,000 MW',
      label: 'High Output / Active Atlantic Flow',
      mae_mw: 740,
      bias_mw: 230,
      periods_count: 440,
      risk_level: 'Elevated',
      risk_color: 'text-warning-text',
      shortfall_pct: 34.1,
    },
    {
      range: '> 12,000 MW',
      label: 'Peak Wind / Storm Cut-Out Exposure',
      mae_mw: 1120,
      bias_mw: -480,
      periods_count: 248,
      risk_level: 'High Shortfall',
      risk_color: 'text-data-shortfall-text',
      shortfall_pct: 54.8,
    },
  ];

  if (!distribution && loading) {
    return (
      <div className="max-w-[1280px] mx-auto px-4 sm:px-6 lg:px-8 py-6 w-full animate-fade-in">
        <div className="h-10 w-96 bg-surface-subtle animate-skeleton rounded mb-6" />
        <div className="h-44 bg-surface border border-border rounded-xl animate-skeleton mb-6" />
      </div>
    );
  }

  return (
    <div className="max-w-[1280px] mx-auto px-4 sm:px-6 lg:px-8 py-6 flex flex-col gap-6 flex-1 w-full animate-fade-in">
      {/* Top Breadcrumb & Page Identity */}
      <div className="flex flex-col gap-2">
        <div className="flex items-center gap-2 text-label text-text-muted uppercase tracking-wider font-semibold">
          <span>ACCURACY ANALYSIS</span>
          <span className="text-border-strong">•</span>
          <span>Granular Attribution &amp; Empirical Risk Sizing</span>
        </div>

        <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
          <div>
            <h1 className="font-h1 text-h1 text-text tracking-tight">
              Error Deep-Dive: 30-Day Failure Modes &amp; Buffer Calibration
            </h1>
            <p className="font-body-sm text-body-sm text-text-muted mt-1 max-w-[72ch]">
              Pinpointing where and when wind forecasts deviate most across January 2026, and calculating empirical procurement safety margins to protect trading desk positions.
            </p>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <button
              type="button"
              onClick={handleExportCsv}
              className="h-9 px-3.5 inline-flex items-center gap-2 bg-surface hover:bg-surface-subtle border border-border-strong text-text font-label text-label rounded-lg transition-colors"
            >
              <Download className="w-4 h-4 text-text-muted" />
              <span>Export Deep-Dive CSV</span>
            </button>
          </div>
        </div>
      </div>

      {/* Parameter Filter Bar */}
      <div className="bg-surface border border-border rounded-xl p-3.5 flex flex-wrap items-center justify-between gap-4">
        <div className="flex flex-wrap items-center gap-3">
          {/* Analysis Period */}
          <div className="flex flex-col">
            <span className="font-label text-[11px] text-text-muted font-medium mb-1">
              Analysis Period
            </span>
            <div className="h-9 px-3 inline-flex items-center gap-2 bg-surface border border-border-strong rounded-lg text-body-sm text-text font-medium">
              <Calendar className="w-4 h-4 text-accent-500" />
              <span>01 Jan 2026 – 31 Jan 2026 · 1,488 SPs</span>
            </div>
          </div>

          {/* Decision Cut-off */}
          <div className="flex flex-col">
            <span className="font-label text-[11px] text-text-muted font-medium mb-1">
              Cut-Off Vintage
            </span>
            <div className="h-9 px-3 inline-flex items-center gap-2 bg-surface border border-border-strong rounded-lg text-body-sm text-text font-medium">
              <Clock className="w-4 h-4 text-accent-500" />
              <span>{cutoff} London (Day-Ahead Lock)</span>
            </div>
          </div>

          {/* Confidence Selector */}
          <div className="flex flex-col">
            <span className="font-label text-[11px] text-text-muted font-medium mb-1">
              Empirical Confidence Level
            </span>
            <div className="h-9 inline-flex p-0.5 bg-surface-subtle border border-border rounded-lg text-body-sm">
              {[80, 90, 95, 99].map((lvl) => (
                <button
                  key={lvl}
                  type="button"
                  onClick={() => setConfidence(lvl)}
                  className={`px-3 py-1 rounded font-medium text-caption transition-colors ${
                    confidence === lvl
                      ? 'bg-surface text-accent-700 font-semibold border border-border shadow-xs'
                      : 'text-text-muted hover:text-text'
                  }`}
                >
                  {lvl}% {confidence === lvl ? '(Selected)' : ''}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Quick Context Tag */}
        <div className="flex items-center gap-2 px-3 py-1.5 bg-surface-subtle border border-border rounded-lg">
          <span className="font-caption text-caption text-text-muted">Aggregate Benchmark:</span>
          <span className="font-code text-caption font-semibold text-text tabular-nums">
            MAE 594 MW · Bias +136 MW
          </span>
        </div>
      </div>

      {/* Tab Navigation (Interactive Filter / Section Switcher) */}
      <div className="border-b border-border">
        <nav className="flex items-center gap-4 sm:gap-6 -mb-px overflow-x-auto no-scrollbar py-1">
          {[
            { id: 'all', label: 'All Failure Modes' },
            { id: 'hour', label: 'By Hour of Day' },
            { id: 'horizon', label: 'By Forecast Horizon' },
            { id: 'level', label: 'By Generation Level' },
            { id: 'distribution', label: 'Error Distribution & Tails' },
            { id: 'buffer', label: 'Procurement Buffer Calibration' },
          ].map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveTab(tab.id as any)}
              className={`h-11 inline-flex items-center px-2 border-b-2 font-body text-body-sm whitespace-nowrap transition-colors ${
                activeTab === tab.id
                  ? 'border-accent-500 text-accent-700 font-semibold'
                  : 'border-transparent text-text-muted hover:text-text font-medium'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {/* Key Finding Callout with Shortfall Accent Bar */}
      <InsightCallout
        type="shortfall"
        title="Key Analytical Finding:"
        body={
          <>
            Forecast error peaks sharply during evening ramp hours (<span className="font-medium text-data-shortfall-text">17:00–20:00 London</span>), with a maximum mean shortfall of <span className="font-code font-semibold tabular-nums">-680 MW</span> at 19:00. Morning ramps (07:00–09:00) exhibit rapid gradient errors resulting in persistent early-cycle under-forecasting against outturn.
          </>
        }
        footerLabel="Empirical Sizing Rule:"
        footerValue={`P${confidence} Mandatory Buffer (${bufferConfig.baseline_buffer_mw} MW)`}
      />

      {/* TAB 1: By Hour of Day (Diurnal) */}
      {(activeTab === 'all' || activeTab === 'hour') && (
        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="font-h3 text-h3 text-text">Diurnal Error Profile (Hour of Day)</h2>
            <span className="text-caption text-text-muted">48 Settlement Periods (24h Diurnal Cycle)</span>
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
            <div className="lg:col-span-8">
              <HourlyErrorChart data={hourlyErrors} />
            </div>

            {/* Hourly Table Summary */}
            <div className="lg:col-span-4 bg-surface border border-border rounded-xl p-5 flex flex-col gap-3">
              <h3 className="font-h4 text-h4 text-text">Critical Diurnal Windows</h3>
              <p className="font-caption text-caption text-text-muted">
                Half-hourly error distribution across UK market trading phases.
              </p>
              <div className="space-y-2 mt-2">
                <div className="p-3 rounded-lg bg-data-shortfall/5 border border-data-shortfall/30">
                  <div className="flex items-center justify-between text-body-sm font-semibold text-data-shortfall-text">
                    <span>Evening Peak (17:00–21:00)</span>
                    <span>-680 MW max</span>
                  </div>
                  <div className="text-caption text-text-muted mt-1">
                    Systemic shortfall window: Actual generation falls behind forecast during peak price hours.
                  </div>
                </div>
                <div className="p-3 rounded-lg bg-surface-subtle border border-border">
                  <div className="flex items-center justify-between text-body-sm font-semibold text-text">
                    <span>Morning Ramp (06:00–12:00)</span>
                    <span>+210 MW bias</span>
                  </div>
                  <div className="text-caption text-text-muted mt-1">
                    Gradient lag: Forecast anticipates ramping earlier than physical turbine spin-up.
                  </div>
                </div>
                <div className="p-3 rounded-lg bg-surface-subtle border border-border">
                  <div className="flex items-center justify-between text-body-sm font-semibold text-text">
                    <span>Overnight Trough (23:00–05:00)</span>
                    <span>±180 MW error</span>
                  </div>
                  <div className="text-caption text-text-muted mt-1">
                    Stable baseline with minimal cashout price volatility.
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>
      )}

      {/* TAB 2: By Generation Level */}
      {(activeTab === 'all' || activeTab === 'level') && (
        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="font-h3 text-h3 text-text">Error Attribution by Generation Tranche</h2>
              <p className="font-caption text-caption text-text-muted">
                Evaluating forecast accuracy across calm, moderate, high, and peak storm generation levels
              </p>
            </div>
            <span className="px-2.5 py-1 rounded-full text-caption font-semibold bg-accent-50 text-accent-700 border border-accent-200">
              1,488 SPs Partitioned
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {generationLevels.map((lvl) => (
              <div key={lvl.range} className="bg-surface border border-border rounded-xl p-5 flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between">
                    <span className="font-code font-bold text-accent-700 text-body-sm">{lvl.range}</span>
                    <span className={`text-caption font-semibold ${lvl.risk_color}`}>{lvl.risk_level}</span>
                  </div>
                  <div className="text-caption text-text-muted mt-1 font-medium">{lvl.label}</div>

                  <div className="mt-4 space-y-2">
                    <div className="flex items-center justify-between text-body-sm">
                      <span className="text-text-muted">MAE:</span>
                      <span className="font-code font-semibold text-text">{lvl.mae_mw} MW</span>
                    </div>
                    <div className="flex items-center justify-between text-body-sm">
                      <span className="text-text-muted">Directional Bias:</span>
                      <span className={`font-code font-semibold ${lvl.bias_mw < 0 ? 'text-data-shortfall-text' : 'text-success'}`}>
                        {lvl.bias_mw > 0 ? `+${lvl.bias_mw}` : lvl.bias_mw} MW
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-body-sm">
                      <span className="text-text-muted">Shortfall Rate:</span>
                      <span className="font-code text-text font-medium">{lvl.shortfall_pct}%</span>
                    </div>
                  </div>
                </div>

                <div className="mt-4 pt-3 border-t border-border text-caption text-text-muted flex justify-between">
                  <span>Sample Size:</span>
                  <span className="font-code font-medium text-text">{lvl.periods_count} SPs</span>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* TAB 3 & 4: Horizon Degradation & Error Distribution */}
      {(activeTab === 'all' || activeTab === 'horizon' || activeTab === 'distribution') && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          {(activeTab === 'all' || activeTab === 'horizon') && (
            <div className={activeTab === 'horizon' ? 'lg:col-span-12' : 'lg:col-span-6'}>
              <HorizonDegradationChart data={horizonCurve} />
            </div>
          )}

          {(activeTab === 'all' || activeTab === 'distribution') && distribution && (
            <div className={activeTab === 'distribution' ? 'lg:col-span-12' : 'lg:col-span-6'}>
              <DistributionHistogram distribution={distribution} />
            </div>
          )}
        </div>
      )}

      {/* TAB 5: Procurement Buffer Calibration */}
      {(activeTab === 'all' || activeTab === 'buffer') && (
        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="font-h3 text-h3 text-text">Procurement Buffer Sizing Engine</h2>
              <p className="font-caption text-caption text-text-muted">
                Reserve holding calibration against asymmetric shortfall tail risk
              </p>
            </div>
            <span className="px-2.5 py-1 rounded-full text-caption font-semibold bg-accent-50 text-accent-700 border border-accent-200">
              Target Guarantee: {confidence}%
            </span>
          </div>

          <div className="bg-surface border border-border rounded-xl p-6 flex flex-col lg:flex-row gap-6">
            {/* Left Buffer Card */}
            <div className="lg:w-1/3 bg-surface-subtle p-5 rounded-xl border border-border flex flex-col justify-between">
              <div>
                <span className="text-caption text-text-muted uppercase font-semibold tracking-wider">
                  Recommended Baseline Hedge
                </span>
                <div className="flex items-baseline gap-2 mt-2">
                  <span className="font-kpi-value text-3xl font-bold text-text tabular-nums">
                    {bufferConfig.baseline_buffer_mw}
                  </span>
                  <span className="font-kpi-unit text-text-muted font-medium">MW Safety Reserve</span>
                </div>
                <p className="font-body-sm text-text-muted mt-2 leading-relaxed">
                  Holding back an average of {bufferConfig.baseline_buffer_mw} MW protects trading positions across {confidence}% of all historical failure modes in January 2026.
                </p>
              </div>

              <div className="pt-4 border-t border-border mt-4">
                <div className="flex items-center gap-2 text-caption text-success font-medium">
                  <ShieldCheck className="w-5 h-5 text-success shrink-0" />
                  <span>Eliminates {bufferConfig.mitigation_effectiveness_pct}% of cashout imbalance penalty</span>
                </div>
              </div>
            </div>

            {/* Right Diurnal Phase Sizing */}
            <div className="lg:w-2/3 space-y-3">
              <h3 className="font-h4 text-h4 text-text">Diurnal Phase Allocation</h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="p-3.5 rounded-lg bg-surface border border-border">
                  <div className="text-caption text-text-muted">Morning Ramp (06:00–12:00)</div>
                  <div className="font-code font-bold text-lg text-text mt-1">+{bufferConfig.morning_ramp_buffer_mw} MW</div>
                  <div className="text-caption text-text-muted mt-0.5">P{confidence} Target for industrial ramp</div>
                </div>

                <div className="p-3.5 rounded-lg bg-surface border border-border">
                  <div className="text-caption text-text-muted">Afternoon Trough (12:00–17:00)</div>
                  <div className="font-code font-bold text-lg text-text mt-1">+{bufferConfig.afternoon_trough_buffer_mw} MW</div>
                  <div className="text-caption text-text-muted mt-0.5">Low variance daylight period</div>
                </div>

                <div className="p-3.5 rounded-lg bg-data-shortfall/5 border border-data-shortfall/30">
                  <div className="text-caption text-data-shortfall-text font-medium">Evening Peak (17:00–21:00)</div>
                  <div className="font-code font-bold text-lg text-data-shortfall-text mt-1">+{bufferConfig.evening_peak_buffer_mw} MW</div>
                  <div className="text-caption text-data-shortfall-text/80 mt-0.5">Mandatory hedge against shortfall window</div>
                </div>

                <div className="p-3.5 rounded-lg bg-surface border border-border">
                  <div className="text-caption text-text-muted">Night Baseline (21:00–06:00)</div>
                  <div className="font-code font-bold text-lg text-text mt-1">+{bufferConfig.night_baseline_buffer_mw} MW</div>
                  <div className="text-caption text-text-muted mt-0.5">Minimal spread risk reserve</div>
                </div>
              </div>
            </div>
          </div>
        </section>
      )}
    </div>
  );
};
