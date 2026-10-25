import React, { useState } from 'react';
import {
  Download,
  Copy,
  Check,
  ChevronDown,
  ChevronUp,
  ShieldCheck,
  Code2,
  Info,
  Layers,
  ArrowRight,
  Clock,
} from 'lucide-react';
import { downloadTextFile } from '../utils/csvExport';

export const MethodologyPage: React.FC = () => {
  const [openAccordion, setOpenAccordion] = useState<string | null>('acc-1');
  const [copiedText, setCopiedText] = useState<string | null>(null);

  const toggleAccordion = (id: string) => {
    setOpenAccordion(openAccordion === id ? null : id);
  };

  const handleCopy = (text: string, label: string) => {
    navigator.clipboard.writeText(text);
    setCopiedText(label);
    setTimeout(() => setCopiedText(null), 2000);
  };

  return (
    <div className="max-w-[1280px] mx-auto px-4 sm:px-6 lg:px-8 py-6 flex-1 w-full animate-fade-in">
      <div className="flex flex-col w-full">
        {/* Eyebrow & Page Header */}
        <div className="mb-6">
          <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4">
            <div>
              <div className="inline-flex items-center gap-1.5 text-text-muted font-label text-label uppercase tracking-wider mb-1">
                <span className="w-1.5 h-1.5 rounded-full bg-accent-500" />
                <span>Governance &amp; Audit Trail · Methodology Specification</span>
              </div>
              <h1 className="font-h1 text-h1 text-text tracking-tight">
                Methodology &amp; Data Reference
              </h1>
              <p className="mt-1.5 text-text-muted font-body text-body max-w-[72ch]">
                Comprehensive documentation of day-ahead cut-off vintages, calculation formulas for forecast error metrics, empirical buffer sizing methodology, and audited Elexon BMRS data feeds.
              </p>
            </div>

            {/* Action Buttons */}
            <div className="flex items-center gap-2 shrink-0">
              <button
                type="button"
                onClick={() => {
                  const specContent = `# Elexon BMRS Wind Generation Forecast Decision Engine v1.4.2
Methodology & Governance Specification
Cut-off Reference: 09:00 London Time (D-1)
Data Coverage: 01 Jan 2026 - 31 Jan 2026 (1,488 Settlement Periods)

1. Decision Cut-off Rules
- BMRS WINDFOR forecasts published after 09:00 London on D-1 are strictly excluded.
- Locked run corresponds to D-1 08:00 publication vintage.

2. Metrics
- Signed Bias: (1/N) * SUM(Forecast - Actual) [MW]
- Mean Absolute Error (MAE): (1/N) * SUM(|Forecast - Actual|) [MW]
- Normalized MAE (NMAE): MAE / 30,200 MW GB metered wind capacity
- WAPE: SUM(|Forecast - Actual|) / SUM(Actual) * 100%
- Shortfall: Period where Actual < Forecast - 200 MW operational deadband

3. Empirical Buffer Calibration
- Buffer(p, h) = Quantile_p(Forecast(h) - Actual(h))
- P90 Evening Peak Buffer: +640 MW
- P90 Daytime Ramp Buffer: +410 MW
- P90 Baseline Buffer: +210 MW

Elexon BMRS Data Copyright 2026. Audited Settlement Run: RF.`;
                  downloadTextFile('bmrs_methodology_specification_v1.4.md', specContent, 'text/markdown;charset=utf-8');
                }}
                className="inline-flex items-center gap-1.5 h-9 px-3 rounded-lg bg-surface border border-border-strong text-text font-label text-label hover:bg-surface-subtle transition-colors shadow-none cursor-pointer"
              >
                <Download className="w-4 h-4 text-accent-500" />
                <span>Download Methodology Spec</span>
              </button>

              <button
                type="button"
                onClick={() =>
                  handleCopy(
                    'Elexon BMRS Wind Generation Forecast Day-Ahead Monitoring Engine, Version 1.4.2 (2026). Available at /api/v1/meta',
                    'citation'
                  )
                }
                className="inline-flex items-center gap-1.5 h-9 px-3 rounded-lg bg-transparent text-text-muted hover:text-text hover:bg-surface-subtle font-label text-label transition-colors cursor-pointer"
              >
                {copiedText === 'citation' ? (
                  <Check className="w-4 h-4 text-success" />
                ) : (
                  <Copy className="w-4 h-4" />
                )}
                <span>{copiedText === 'citation' ? 'Copied Citation' : 'Copy Citation'}</span>
              </button>
            </div>
          </div>
        </div>

        {/* Two-Column Layout */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 lg:gap-8 items-start">
          {/* Main Reading Column (8 cols) */}
          <div className="lg:col-span-8 flex flex-col gap-8 min-w-0">
            {/* SECTION 1 */}
            <section id="section-1" className="scroll-mt-20">
              <div className="flex items-center gap-2 mb-2">
                <span className="text-accent-500 font-label text-label uppercase tracking-widest font-semibold">
                  01
                </span>
                <h2 className="font-h2 text-h2 text-text">How the day-ahead forecast is chosen</h2>
              </div>
              <p className="font-body text-body text-text leading-relaxed max-w-[72ch] mb-4">
                To mirror trading desk decision-making for power procurement, the monitor freezes national wind generation forecasts at a strict decision cut-off—defaulting to 09:00 London time on Day-Ahead (D-1). Under GB wholesale market operations, trading desks must commit positions into day-ahead auctions (such as EPEX SPOT and Nord Pool) between 09:30 and 11:00 London time. Any forecast publication received after the 09:00 cut-off is strictly excluded from decision metrics to prevent look-ahead bias.
              </p>

              {/* Timeline SVG */}
              <div className="bg-surface border border-border rounded-xl p-5 md:p-6 shadow-card">
                <div className="flex items-center justify-between mb-3 text-text-muted font-label text-label">
                  <span className="font-medium text-text">D-1 VINTAGE TIMELINE &amp; AUCTION GATE COUPLING</span>
                  <span className="font-code text-code">TZ: Europe/London</span>
                </div>

                <div className="w-full overflow-x-auto">
                  <svg className="w-full min-w-[620px] h-[140px]" viewBox="0 0 680 140" fill="none">
                    <line x1="40" x2="40" y1="20" y2="90" stroke="#E5E5E0" strokeDasharray="2 2" strokeWidth="1" />
                    <line x1="140" x2="140" y1="20" y2="90" stroke="#E5E5E0" strokeDasharray="2 2" strokeWidth="1" />
                    <line x1="230" x2="230" y1="20" y2="90" stroke="#E5E5E0" strokeDasharray="2 2" strokeWidth="1" />
                    <line x1="320" x2="320" y1="20" y2="90" stroke="#E5E5E0" strokeDasharray="2 2" strokeWidth="1" />
                    <line x1="490" x2="490" y1="20" y2="90" stroke="#E5E5E0" strokeDasharray="2 2" strokeWidth="1" />
                    <line x1="610" x2="610" y1="20" y2="90" stroke="#E5E5E0" strokeDasharray="2 2" strokeWidth="1" />

                    <line x1="30" x2="650" y1="65" y2="65" stroke="#CFCFC8" strokeWidth="2" />

                    {/* Auction Window Shading */}
                    <rect x="360" y="24" width="75" height="52" rx="3" fill="#D9E5F0" fillOpacity="0.5" />
                    <text x="397.5" y="44" textAnchor="middle" fill="#104571" fontSize="10" fontWeight="600">
                      AUCTION WINDOW
                    </text>
                    <text x="397.5" y="58" textAnchor="middle" fill="#264C71" fontSize="9">
                      09:30 – 11:00
                    </text>

                    {/* Vintages */}
                    <circle cx="50" cy="65" r="4.5" fill="#FFFFFF" stroke="#B8BEC4" strokeWidth="2" />
                    <text x="50" y="85" textAnchor="middle" fill="#5F6B76" fontSize="10" className="font-code">D-2 18:00</text>
                    <text x="50" y="98" textAnchor="middle" fill="#9AA3AB" fontSize="9">ECMWF base</text>

                    <circle cx="140" cy="65" r="4.5" fill="#FFFFFF" stroke="#B8BEC4" strokeWidth="2" />
                    <text x="140" y="85" textAnchor="middle" fill="#5F6B76" fontSize="10" className="font-code">D-1 02:00</text>
                    <text x="140" y="98" textAnchor="middle" fill="#9AA3AB" fontSize="9">Overnight run</text>

                    <circle cx="230" cy="65" r="4.5" fill="#FFFFFF" stroke="#B8BEC4" strokeWidth="2" />
                    <text x="230" y="85" textAnchor="middle" fill="#5F6B76" fontSize="10" className="font-code">D-1 05:00</text>
                    <text x="230" y="98" textAnchor="middle" fill="#9AA3AB" fontSize="9">Early update</text>

                    {/* Selected D-1 08:00 Locked Run */}
                    <circle cx="320" cy="65" r="7" fill="#2F5D8A" />
                    <circle cx="320" cy="65" r="11" stroke="#2F5D8A" strokeOpacity="0.3" strokeWidth="1.5" />
                    <text x="320" y="85" textAnchor="middle" fill="#104571" fontSize="10" fontWeight="600" className="font-code">D-1 08:00</text>
                    <text x="320" y="98" textAnchor="middle" fill="#2F5D8A" fontSize="9" fontWeight="600">Locked Run</text>

                    {/* Cut-off Line */}
                    <line x1="360" x2="360" y1="12" y2="88" stroke="#B42318" strokeDasharray="3 3" strokeWidth="1.5" />
                    <rect x="322" y="10" width="76" height="18" rx="4" fill="#FFDAD6" />
                    <text x="360" y="22" textAnchor="middle" fill="#93000A" fontSize="9.5" fontWeight="600">09:00 CUT-OFF</text>

                    {/* Post-cutoff */}
                    <circle cx="490" cy="65" r="4.5" fill="#FFFFFF" stroke="#B8BEC4" strokeDasharray="2 2" strokeWidth="1.5" />
                    <text x="490" y="85" textAnchor="middle" fill="#9AA3AB" fontSize="10" className="font-code">D-1 14:00</text>
                    <text x="490" y="98" textAnchor="middle" fill="#9AA3AB" fontSize="9">Excluded</text>

                    <circle cx="610" cy="65" r="4.5" fill="#FFFFFF" stroke="#B8BEC4" strokeDasharray="2 2" strokeWidth="1.5" />
                    <text x="610" y="85" textAnchor="middle" fill="#9AA3AB" fontSize="10" className="font-code">D-0 Gate</text>
                    <text x="610" y="98" textAnchor="middle" fill="#9AA3AB" fontSize="9">Intraday</text>
                  </svg>
                </div>

                <div className="mt-3 pt-3 border-t border-border flex flex-wrap items-center gap-x-6 gap-y-2 text-text-muted font-caption text-caption">
                  <div className="flex items-center gap-1.5">
                    <span className="w-2.5 h-2.5 rounded-full bg-accent-500" />
                    <span>Selected Decision Vintage (08:00 Run locked at 09:00)</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className="w-2.5 h-2.5 rounded-full border border-border-strong bg-surface" />
                    <span>Unused Prior Vintages</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className="w-2.5 h-2.5 rounded-full border border-dashed border-border-strong bg-surface" />
                    <span>Excluded Post-Cutoff Runs</span>
                  </div>
                </div>
              </div>
            </section>

            {/* SECTION 2 */}
            <section id="section-2" className="scroll-mt-20">
              <div className="flex items-center gap-2 mb-2">
                <span className="text-accent-500 font-label text-label uppercase tracking-widest font-semibold">
                  02
                </span>
                <h2 className="font-h2 text-h2 text-text">Metrics and sign convention</h2>
              </div>
              <p className="font-body text-body text-text leading-relaxed max-w-[72ch] mb-4">
                Every error metric enforces a strict physical convention: error = Forecast minus Actual outturn (or Delta = Actual minus Forecast, as detailed per metric). In this monitor, buyer deficit risk is unequivocally labelled as Shortfall.
              </p>

              {/* Accordions */}
              <div className="flex flex-col gap-3">
                {/* Accordion 1 */}
                <div className="bg-surface border border-border rounded-lg overflow-hidden shadow-card">
                  <button
                    type="button"
                    onClick={() => toggleAccordion('acc-1')}
                    className="w-full px-4 py-3 bg-surface text-left flex items-center justify-between hover:bg-surface-subtle transition-colors cursor-pointer"
                  >
                    <div className="flex items-center gap-2.5">
                      <span className="w-2 h-2 rounded-full bg-accent-500" />
                      <span className="font-h4 text-h4 text-text">Signed Error &amp; Directional Bias</span>
                    </div>
                    {openAccordion === 'acc-1' ? (
                      <ChevronUp className="w-5 h-5 text-text-muted" />
                    ) : (
                      <ChevronDown className="w-5 h-5 text-text-muted" />
                    )}
                  </button>
                  {openAccordion === 'acc-1' && (
                    <div className="px-4 pb-4 pt-1 border-t border-border bg-surface animate-fade-in">
                      <p className="font-body-sm text-body-sm text-text-muted mb-2.5">
                        Directional bias measures whether models systematically over- or under-predict aggregate volume across a defined evaluation window.
                      </p>
                      <div className="bg-surface-subtle border border-border rounded-md p-3 mb-2 font-code text-code text-text">
                        Bias = (1 / N) * ∑ (Forecast_t - Actual_t) [MW]
                      </div>
                      <p className="font-caption text-caption text-text-muted">
                        <strong>Interpretation:</strong> A positive bias (+MW) indicates systemic over-forecasting (desk bought excess power, exposed to System Buy Price down-regulation). A negative bias (-MW) indicates systemic under-forecasting.
                      </p>
                    </div>
                  )}
                </div>

                {/* Accordion 2 */}
                <div className="bg-surface border border-border rounded-lg overflow-hidden shadow-card">
                  <button
                    type="button"
                    onClick={() => toggleAccordion('acc-2')}
                    className="w-full px-4 py-3 bg-surface text-left flex items-center justify-between hover:bg-surface-subtle transition-colors cursor-pointer"
                  >
                    <div className="flex items-center gap-2.5">
                      <span className="w-2 h-2 rounded-full bg-border-strong" />
                      <span className="font-h4 text-h4 text-text">Mean Absolute Error (MAE) &amp; Normalized MAE</span>
                    </div>
                    {openAccordion === 'acc-2' ? (
                      <ChevronUp className="w-5 h-5 text-text-muted" />
                    ) : (
                      <ChevronDown className="w-5 h-5 text-text-muted" />
                    )}
                  </button>
                  {openAccordion === 'acc-2' && (
                    <div className="px-4 pb-4 pt-1 border-t border-border bg-surface animate-fade-in">
                      <p className="font-body-sm text-body-sm text-text-muted mb-2.5">
                        Evaluates aggregate forecast dispersion irrespective of direction. Reflects overall prediction precision across settlement periods.
                      </p>
                      <div className="bg-surface-subtle border border-border rounded-md p-3 mb-2 font-code text-code text-text">
                        MAE = (1 / N) * ∑ |Forecast_t - Actual_t| [MW]
                      </div>
                      <p className="font-caption text-caption text-text-muted">
                        <strong>Normalization:</strong> Normalized by total GB wind metered capacity (currently 30.2 GW, yielding 594 MW = 7.1% NMAE for the audited January baseline).
                      </p>
                    </div>
                  )}
                </div>

                {/* Accordion 3 */}
                <div className="bg-surface border border-border rounded-lg overflow-hidden shadow-card">
                  <button
                    type="button"
                    onClick={() => toggleAccordion('acc-3')}
                    className="w-full px-4 py-3 bg-surface text-left flex items-center justify-between hover:bg-surface-subtle transition-colors cursor-pointer"
                  >
                    <div className="flex items-center gap-2.5">
                      <span className="w-2 h-2 rounded-full bg-data-shortfall" />
                      <span className="font-h4 text-h4 text-text">Shortfall Depth &amp; Shortfall Frequency (Buyer Risk)</span>
                    </div>
                    {openAccordion === 'acc-3' ? (
                      <ChevronUp className="w-5 h-5 text-text-muted" />
                    ) : (
                      <ChevronDown className="w-5 h-5 text-text-muted" />
                    )}
                  </button>
                  {openAccordion === 'acc-3' && (
                    <div className="px-4 pb-4 pt-1 border-t border-border bg-surface animate-fade-in">
                      <p className="font-body-sm text-body-sm text-text-muted mb-2.5">
                        Measures unhedged exposure where physical generation fails to meet contracted day-ahead commitments beyond the trading operational tolerance threshold.
                      </p>
                      <div className="bg-surface-subtle border border-border rounded-md p-3 mb-2 font-code text-code text-text">
                        Shortfall Event = Actual_t &lt; (Forecast_t - 200 MW threshold)
                      </div>
                      <p className="font-caption text-caption text-text-muted">
                        <strong>Market Consequence:</strong> Shortfall forces the buyer into cashout imbalance exposure at System Sell Price (SSP), historically the highest financial penalty state during cold/low-wind crunches.
                      </p>
                    </div>
                  )}
                </div>

                {/* Accordion 4 */}
                <div className="bg-surface border border-border rounded-lg overflow-hidden shadow-card">
                  <button
                    type="button"
                    onClick={() => toggleAccordion('acc-4')}
                    className="w-full px-4 py-3 bg-surface text-left flex items-center justify-between hover:bg-surface-subtle transition-colors cursor-pointer"
                  >
                    <div className="flex items-center gap-2.5">
                      <span className="w-2 h-2 rounded-full bg-border-strong" />
                      <span className="font-h4 text-h4 text-text">Weighted Absolute Percentage Error (WAPE) &amp; RMSE</span>
                    </div>
                    {openAccordion === 'acc-4' ? (
                      <ChevronUp className="w-5 h-5 text-text-muted" />
                    ) : (
                      <ChevronDown className="w-5 h-5 text-text-muted" />
                    )}
                  </button>
                  {openAccordion === 'acc-4' && (
                    <div className="px-4 pb-4 pt-1 border-t border-border bg-surface animate-fade-in">
                      <p className="font-body-sm text-body-sm text-text-muted mb-2.5">
                        Penalises volume errors proportionally across high and low generation days, preventing mathematical explosions caused by near-zero denominators.
                      </p>
                      <div className="bg-surface-subtle border border-border rounded-md p-3 mb-2 font-code text-code text-text">
                        WAPE = (∑ |Forecast_t - Actual_t|) / (∑ Actual_t) * 100%
                      </div>
                      <p className="font-caption text-caption text-text-muted">
                        <strong>Root Mean Squared Error (RMSE):</strong> Calculated as √(1/N * ∑(Forecast_t - Actual_t)²), providing extra weighting to catastrophic tail drops (&gt;1,500 MW single-period errors).
                      </p>
                    </div>
                  )}
                </div>
              </div>
            </section>

            {/* SECTION 3 */}
            <section id="section-3" className="scroll-mt-20">
              <div className="flex items-center gap-2 mb-2">
                <span className="text-accent-500 font-label text-label uppercase tracking-widest font-semibold">
                  03
                </span>
                <h2 className="font-h2 text-h2 text-text">Empirical buffer sizing methodology</h2>
              </div>
              <p className="font-body text-body text-text leading-relaxed max-w-[72ch] mb-4">
                Rather than applying a flat percentage haircut, the operational safety buffer is derived from the empirical non-parametric quantile distribution of historical errors across 1,488 verified settlement periods (January 2026).
              </p>

              <div className="bg-surface border border-border rounded-xl p-5 md:p-6 shadow-card">
                <div className="font-code text-code bg-surface-subtle border border-border rounded-md p-3 mb-4 text-text">
                  Buffer(p, h) = Q_p (Forecast(h) - Actual(h))
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-body-sm font-body-sm">
                  <div className="flex flex-col gap-1.5">
                    <span className="text-text font-medium">Confidence Level (p)</span>
                    <p className="text-text-muted">
                      Quantile calibration parameter (P80, P90, or P95). At P90, the buffer covers 90% of observed historical under-generation shortfalls.
                    </p>
                  </div>
                  <div className="flex flex-col gap-1.5">
                    <span className="text-text font-medium">Diurnal Partitioning (h)</span>
                    <p className="text-text-muted">
                      Separate calibration distributions are computed for 4 distinct operating diurnal blocks: Morning Ramp (06:00–12:00), Afternoon Trough (12:00–17:00), Evening Peak (17:00–21:00), and Night Baseline (21:00–06:00).
                    </p>
                  </div>
                </div>

                <div className="mt-4 pt-3 border-t border-border flex items-start gap-2 bg-surface-subtle p-3 rounded-lg">
                  <Info className="w-5 h-5 text-warning-fill shrink-0 mt-0.5" />
                  <p className="font-caption text-caption text-text-muted">
                    <strong className="text-text font-medium">Evening Peak Asymmetry:</strong> During the Evening Peak (17:00–21:00 London time), thermal ramping constraints in the GB transmission system create pronounced asymmetric shortfall tails, demanding a <span className="font-code text-code text-text font-medium">+640 MW</span> safety buffer at P90 versus only <span className="font-code text-code text-text font-medium">+210 MW</span> during night baselines.
                  </p>
                </div>
              </div>
            </section>

            {/* SECTION 4 */}
            <section id="section-4" className="scroll-mt-20">
              <div className="flex items-center gap-2 mb-2">
                <span className="text-accent-500 font-label text-label uppercase tracking-widest font-semibold">
                  04
                </span>
                <h2 className="font-h2 text-h2 text-text">Data sources &amp; pipeline architecture</h2>
              </div>
              <p className="font-body text-body text-text leading-relaxed max-w-[72ch] mb-4">
                The ingestion pipeline ingests raw telemetry via official Elexon Balancing Mechanism Reporting Service (BMRS) feeds and National Grid ESO APIs with sub-15 minute validation guarantees.
              </p>

              <div className="bg-surface border border-border rounded-xl overflow-hidden shadow-card">
                <div className="overflow-x-auto">
                  <table className="w-full text-left border-collapse">
                    <thead>
                      <tr className="bg-surface-subtle border-b border-border">
                        <th className="py-2.5 px-4 font-label text-label text-text-muted uppercase">Feed Name</th>
                        <th className="py-2.5 px-4 font-label text-label text-text-muted uppercase">Source Entity</th>
                        <th className="py-2.5 px-4 font-label text-label text-text-muted uppercase">Update Frequency</th>
                        <th className="py-2.5 px-4 font-label text-label text-text-muted uppercase text-right">Settlement Lag</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border font-body-sm text-body-sm text-text">
                      <tr className="hover:bg-surface-subtle transition-colors">
                        <td className="py-3 px-4 font-medium">
                          <span className="font-code text-code text-accent-500">BMRS WINDFOR</span>
                          <span className="block text-caption text-text-muted">Wind Generation Forecast</span>
                        </td>
                        <td className="py-3 px-4 text-text-muted">Elexon Portal BMRS / Data API</td>
                        <td className="py-3 px-4">Half-hourly updates</td>
                        <td className="py-3 px-4 text-right font-code text-code text-text-muted">&lt; 12 mins</td>
                      </tr>
                      <tr className="hover:bg-surface-subtle transition-colors">
                        <td className="py-3 px-4 font-medium">
                          <span className="font-code text-code text-accent-500">BMRS FUELHH</span>
                          <span className="block text-caption text-text-muted">Outturn Generation by Fuel</span>
                        </td>
                        <td className="py-3 px-4 text-text-muted">National Grid ESO Metering</td>
                        <td className="py-3 px-4">Published SP + 15m</td>
                        <td className="py-3 px-4 text-right font-code text-code text-text-muted">Initial: +15m · Final: RF</td>
                      </tr>
                      <tr className="hover:bg-surface-subtle transition-colors">
                        <td className="py-3 px-4 font-medium">
                          <span className="font-code text-code text-accent-500">BMRS DERIVED</span>
                          <span className="block text-caption text-text-muted">System Imbalance Prices (SSP/SBP)</span>
                        </td>
                        <td className="py-3 px-4 text-text-muted">Elexon Settlement Admin</td>
                        <td className="py-3 px-4">Settlement Period + 30m</td>
                        <td className="py-3 px-4 text-right font-code text-code text-text-muted">Cashout audit run</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            </section>

            {/* SECTION 5 */}
            <section id="section-5" className="scroll-mt-20">
              <div className="flex items-center gap-2 mb-2">
                <span className="text-accent-500 font-label text-label uppercase tracking-widest font-semibold">
                  05
                </span>
                <h2 className="font-h2 text-h2 text-text">Data freshness &amp; integrity audit</h2>
              </div>

              <div className="bg-surface border border-border rounded-xl p-5 md:p-6 shadow-card">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-border gap-2">
                  <div className="flex items-center gap-2">
                    <ShieldCheck className="w-5 h-5 text-accent-500" />
                    <span className="font-h4 text-h4 text-text">BMRS INGEST &amp; VERIFICATION AUDIT</span>
                  </div>
                  <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-success/10 border border-success/30 text-success font-caption text-caption">
                    <span className="w-1.5 h-1.5 rounded-full bg-success" />
                    <span className="font-medium">Status: Operational · 100% Locked</span>
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4 py-4 border-b border-border">
                  <div>
                    <div className="font-label text-label text-text-muted uppercase mb-1">Audited Range</div>
                    <div className="font-h4 text-h4 text-text font-semibold">01 Jan – 31 Jan 2026</div>
                    <div className="font-caption text-caption text-text-muted mt-0.5">31 Days (1,488 SPs)</div>
                  </div>
                  <div>
                    <div className="font-label text-label text-text-muted uppercase mb-1">Last Pipeline Ingest</div>
                    <div className="font-h4 text-h4 text-text font-semibold">24 Oct 2026 · 09:02 UTC</div>
                    <div className="font-caption text-caption text-text-muted mt-0.5">Automated validation passed</div>
                  </div>
                  <div>
                    <div className="font-label text-label text-text-muted uppercase mb-1">Validated Rows Loaded</div>
                    <div className="font-h4 text-h4 text-text font-semibold tabular-nums">1,488 / 1,488 SPs</div>
                    <div className="font-caption text-caption text-text-muted mt-0.5">Zero missing intervals</div>
                  </div>
                  <div>
                    <div className="font-label text-label text-text-muted uppercase mb-1">Rejected / Out-of-Bounds</div>
                    <div className="font-h4 text-h4 text-text font-semibold tabular-nums">0 Records (0.00%)</div>
                    <div className="font-caption text-caption text-text-muted mt-0.5">Checksum verification OK</div>
                  </div>
                </div>

                <div className="pt-3 flex flex-col sm:flex-row sm:items-center justify-between text-text-muted font-code text-code gap-2 text-xs">
                  <span className="truncate">SHA-256 Checksum: 8f4e29b1d70e4a68c92a953e5ffb12c03a</span>
                  <span className="shrink-0 font-sans font-caption text-caption">
                    Settlement Run: <strong className="text-text">RF (Reconciliation Final)</strong>
                  </span>
                </div>
              </div>
            </section>

            {/* SECTION 6 */}
            <section id="section-6" className="scroll-mt-20">
              <div className="flex items-center gap-2 mb-2">
                <span className="text-accent-500 font-label text-label uppercase tracking-widest font-semibold">
                  06
                </span>
                <h2 className="font-h2 text-h2 text-text">Key assumptions &amp; operating boundaries</h2>
              </div>

              <div className="bg-surface border border-border rounded-xl divide-y divide-border shadow-card">
                <div className="p-5 flex items-start gap-3">
                  <Layers className="w-5 h-5 text-secondary shrink-0 mt-0.5" />
                  <div>
                    <h4 className="font-h4 text-h4 text-text mb-1">Transmission Constraints &amp; Curtailment</h4>
                    <p className="font-body-sm text-body-sm text-text-muted leading-relaxed">
                      National forecasts reflect gross aggregate GB output. Localised transmission bottlenecks (e.g., B6 Scottish-English boundary curtailment managed via Bid-Offer Acceptances in the Balancing Mechanism) are accounted for via BM unit aggregate telemetry to avoid mistaking curtailment down-regulation for intrinsic weather forecast error.
                    </p>
                  </div>
                </div>

                <div className="p-5 flex items-start gap-3">
                  <Info className="w-5 h-5 text-secondary shrink-0 mt-0.5" />
                  <div>
                    <h4 className="font-h4 text-h4 text-text mb-1">Offshore vs Onshore Blending</h4>
                    <p className="font-body-sm text-body-sm text-text-muted leading-relaxed">
                      BMRS WINDFOR aggregates both onshore and offshore capacity without distinct sub-regional weighting. Our model normalizes outturn capacity according to the National Grid ESO active registered generation register (30.2 GW metered baseline).
                    </p>
                  </div>
                </div>

                <div className="p-5 flex items-start gap-3">
                  <Clock className="w-5 h-5 text-secondary shrink-0 mt-0.5" />
                  <div>
                    <h4 className="font-h4 text-h4 text-text mb-1">Settlement Clock &amp; Boundary Handling</h4>
                    <p className="font-body-sm text-body-sm text-text-muted leading-relaxed">
                      All settlement periods adhere to Europe/London local time (SP 01: 00:00–00:30, SP 48: 23:30–24:00). Clock changes (23-hour and 25-hour days during daylight saving shifts) are normalized via UTC timestamp matching in all programmatic export payloads.
                    </p>
                  </div>
                </div>
              </div>
            </section>

            {/* SECTION 7 */}
            <section id="section-7" className="scroll-mt-20">
              <div className="flex items-center gap-2 mb-2">
                <span className="text-accent-500 font-label text-label uppercase tracking-widest font-semibold">
                  07
                </span>
                <h2 className="font-h2 text-h2 text-text">Attribution, license &amp; data export</h2>
              </div>
              <p className="font-body text-body text-text leading-relaxed max-w-[72ch] mb-4">
                Contains BMRS data © Elexon Limited copyright and database right 2026. All analytics, quantile calculations, and buffer recommendations are produced independently by the Wind Forecast Monitor engine.
              </p>

              {/* Programmatic Endpoints */}
              <div className="flex flex-col gap-3">
                <div className="bg-surface-subtle border border-border rounded-lg p-3.5 shadow-xs">
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="font-label text-label uppercase text-text-muted font-medium">
                      Cut-off Forecast Extract
                    </span>
                    <span className="text-success font-code text-code font-medium">GET JSON / CSV</span>
                  </div>
                  <div className="flex items-center justify-between gap-2">
                    <code className="font-code text-code text-text select-all overflow-x-auto">
                      GET /api/v1/day-ahead?decision_date=2026-01-15&amp;cutoff=09:00
                    </code>
                    <button
                      type="button"
                      onClick={() =>
                        handleCopy('GET /api/v1/day-ahead?decision_date=2026-01-15&cutoff=09:00', 'ep1')
                      }
                      className="p-1 hover:bg-surface rounded text-text-muted hover:text-text shrink-0 cursor-pointer"
                      title="Copy Endpoint"
                    >
                      {copiedText === 'ep1' ? (
                        <Check className="w-4 h-4 text-success" />
                      ) : (
                        <Copy className="w-4 h-4" />
                      )}
                    </button>
                  </div>
                </div>

                <div className="bg-surface-subtle border border-border rounded-lg p-3.5 shadow-xs">
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="font-label text-label uppercase text-text-muted font-medium">
                      Accuracy &amp; Quantile Buffer API
                    </span>
                    <span className="text-success font-code text-code font-medium">GET JSON</span>
                  </div>
                  <div className="flex items-center justify-between gap-2">
                    <code className="font-code text-code text-text select-all overflow-x-auto">
                      GET /api/v1/accuracy/summary?from=2026-01-01&amp;to=2026-01-31&amp;cutoff=09:00
                    </code>
                    <button
                      type="button"
                      onClick={() =>
                        handleCopy(
                          'GET /api/v1/accuracy/summary?from=2026-01-01&to=2026-01-31&cutoff=09:00',
                          'ep2'
                        )
                      }
                      className="p-1 hover:bg-surface rounded text-text-muted hover:text-text shrink-0 cursor-pointer"
                      title="Copy Endpoint"
                    >
                      {copiedText === 'ep2' ? (
                        <Check className="w-4 h-4 text-success" />
                      ) : (
                        <Copy className="w-4 h-4" />
                      )}
                    </button>
                  </div>
                </div>
              </div>
            </section>
          </div>

          {/* Sticky Table of Contents (Desktop sidebar 4 cols) */}
          <div className="lg:col-span-4 sticky top-24 flex flex-col gap-4 hidden lg:flex">
            <div className="bg-surface border border-border rounded-xl p-5 shadow-card">
              <div className="text-text-muted font-label text-label uppercase tracking-wider mb-3 font-semibold">
                On This Page
              </div>
              <nav className="flex flex-col gap-1">
                {[
                  { id: 'section-1', title: '1. Day-Ahead Selection & Cut-off' },
                  { id: 'section-2', title: '2. Metrics & Sign Conventions' },
                  { id: 'section-3', title: '3. Buffer Calibration Model' },
                  { id: 'section-4', title: '4. Data Sources & Feeds' },
                  { id: 'section-5', title: '5. Freshness & Audit Registry' },
                  { id: 'section-6', title: '6. Assumptions & Guardrails' },
                  { id: 'section-7', title: '7. Attribution & Access' },
                ].map((item) => (
                  <a
                    key={item.id}
                    href={`#${item.id}`}
                    className="flex items-center justify-between py-1.5 px-2.5 rounded-md font-body-sm text-body-sm text-text-muted hover:text-text hover:bg-surface-subtle transition-colors"
                  >
                    <span>{item.title}</span>
                    <ArrowRight className="w-3.5 h-3.5 opacity-60" />
                  </a>
                ))}
              </nav>
            </div>

            {/* Quick Info Box */}
            <div className="bg-surface-subtle border border-border rounded-xl p-4 flex flex-col gap-2.5 text-caption font-caption text-text-muted">
              <div className="flex items-center justify-between">
                <span className="font-medium text-text">Engine Version</span>
                <span className="font-code text-code text-text">v1.4.2</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="font-medium text-text">Governance Status</span>
                <span className="text-success font-medium">Audited &amp; Reconciled</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="font-medium text-text">Decision Window</span>
                <span className="font-code text-code text-text">January 2026</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
