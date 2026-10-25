import React, { useState } from 'react';
import { SettlementPeriodRecord, VintageCurve } from '../../api/types';

interface DayExplorerChartsProps {
  records: SettlementPeriodRecord[];
  vintages: VintageCurve[];
  onPeriodSelect?: (period: number) => void;
  selectedPeriod?: number | null;
}

export const DayExplorerCharts: React.FC<DayExplorerChartsProps> = ({
  records,
  vintages,
  onPeriodSelect,
  selectedPeriod = 28,
}) => {
  const [hoveredSP, setHoveredSP] = useState<number | null>(selectedPeriod);

  // Coordinates
  const xStart = 60;
  const xEnd = 975;
  const count = records.length || 48;
  const dx = (xEnd - xStart) / (count - 1);

  // Y-axis 0 to 14,000 MW. Baseline y=280 (0 MW), Top y=20 (14,000 MW). Height = 260px.
  const yBase = 280;
  const maxMw = 14000;
  const scaleY = (mw: number) => yBase - (mw / maxMw) * 260;

  // Forecast polyline
  const fcPoints = records.map((r, i) => `${xStart + i * dx},${scaleY(r.forecast_mw)}`).join(' ');

  // Actual polyline
  const actPoints = records.map((r, i) => `${xStart + i * dx},${scaleY(r.actual_mw ?? r.forecast_mw)}`).join(' ');

  // 09:00 Cut-off X (period 18: idx 17)
  const cutoffX = xStart + 17 * dx;

  // Active hover info
  const activeRecord = hoveredSP != null ? records[hoveredSP - 1] : records[27];
  const activeX = activeRecord ? xStart + (activeRecord.period - 1) * dx : 0;
  const activeFcY = activeRecord ? scaleY(activeRecord.forecast_mw) : 0;
  const activeActY = activeRecord && activeRecord.actual_mw != null ? scaleY(activeRecord.actual_mw) : 0;

  // Sub-chart error bars: Y zero line at y=55. +1000MW at y=15, -1000MW at y=95.
  // 1000 MW = 40px (0.04 px / MW)
  const errYZero = 55;
  const errScale = 0.04;

  return (
    <div className="space-y-6">
      {/* Chart A: Forecast vs Outturn & Error Bars */}
      <div className="bg-surface border border-border rounded-xl overflow-hidden">
        {/* Card Header */}
        <div className="p-5 border-b border-border flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <h2 className="font-h3 text-h3 text-text">
                Day-Ahead Forecast vs Outturn Generation
              </h2>
              <span className="px-2 py-0.5 rounded text-caption font-caption bg-surface-subtle border border-border text-text-muted">
                48 Settlement Periods
              </span>
            </div>
            <p className="font-body-sm text-body-sm text-text-muted mt-0.5">
              Half-hourly power (MW) across 48 settlement periods · 16 Jan 2026
            </p>
          </div>
        </div>

        {/* Legend */}
        <div className="px-5 py-3 bg-surface-subtle border-b border-border flex flex-wrap items-center justify-between gap-y-2 gap-x-6 font-caption text-caption">
          <div className="flex flex-wrap items-center gap-5">
            <div className="flex items-center gap-2">
              <span className="w-4 h-0.5 bg-[#2F5D8A] inline-block" />
              <span className="text-text font-medium">Forecast (09:00 Cut-off Lock)</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-4 h-0.5 bg-[#1F2933] inline-block" />
              <span className="text-text font-medium">Actual Outturn Generation</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-3 h-2.5 bg-[#C2571A] inline-block rounded-xs" />
              <span className="text-text-muted">Shortfall (Actual &lt; Forecast)</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-3 h-2.5 bg-[#2E7D6B] inline-block rounded-xs" />
              <span className="text-text-muted">Surplus (Actual &gt; Forecast)</span>
            </div>
          </div>
          <div className="flex items-center gap-2 text-text-muted">
            <span className="w-4 border-b border-dashed border-[#5F6B76] inline-block" />
            <span>D-1 09:00 Gate Lock Reference</span>
          </div>
        </div>

        {/* Main Forecast vs Actual SVG */}
        <div className="p-5 overflow-x-auto">
          <div className="min-w-[840px] w-full">
            <svg
              className="w-full h-auto select-none font-caption"
              viewBox="0 0 1000 340"
              style={{ display: 'block' }}
            >
              <defs>
                <linearGradient id="dayBufferGrad" x1="0" x2="0" y1="0" y2="1">
                  <stop offset="0%" stopColor="#2F5D8A" stopOpacity="0.10" />
                  <stop offset="100%" stopColor="#2F5D8A" stopOpacity="0.02" />
                </linearGradient>
              </defs>

              {/* Gridlines */}
              {[
                { mw: 14000, label: '14,000 MW', y: 20 },
                { mw: 10500, label: '10,500 MW', y: 85 },
                { mw: 7000, label: '7,000 MW', y: 150 },
                { mw: 3500, label: '3,500 MW', y: 215 },
                { mw: 0, label: '0 MW', y: 280 },
              ].map((g) => (
                <g key={g.mw}>
                  <line
                    x1="55"
                    x2="980"
                    y1={g.y}
                    y2={g.y}
                    stroke={g.mw === 0 ? '#1F2933' : '#E5E5E0'}
                    strokeWidth={g.mw === 0 ? '1.2' : '1'}
                    strokeDasharray={g.mw === 0 ? undefined : '2 2'}
                  />
                  <text x="48" y={g.y + 4} textAnchor="end" className="fill-[#5F6B76] font-code text-[11px]">
                    {g.label}
                  </text>
                </g>
              ))}

              {/* Vertical Time Lines */}
              {[
                { sp: 1, time: '00:00', x: 60 },
                { sp: 8, time: '04:00', x: 193 },
                { sp: 16, time: '08:00', x: 345 },
                { sp: 24, time: '12:00', x: 498 },
                { sp: 32, time: '16:00', x: 650 },
                { sp: 40, time: '20:00', x: 803 },
                { sp: 48, time: '24:00', x: 975 },
              ].map((t) => (
                <g key={t.sp}>
                  <line x1={t.x} x2={t.x} y1="20" y2="280" stroke="#E5E5E0" strokeWidth="1" strokeDasharray="2 2" />
                  <text x={t.x} y="298" textAnchor="middle" className="fill-[#5F6B76] font-code text-[10px]">
                    {t.time}
                  </text>
                  <text x={t.x} y="312" textAnchor="middle" className="fill-[#9AA3AB] font-code text-[9px]">
                    SP {String(t.sp).padStart(2, '0')}
                  </text>
                </g>
              ))}

              {/* Cut-off marker */}
              <line x1={cutoffX} x2={cutoffX} y1="16" y2="280" stroke="#5F6B76" strokeWidth="1.5" strokeDasharray="4 4" />
              <rect x={cutoffX - 40} y="10" width="80" height="18" rx="3" fill="#F4F4EF" stroke="#CFCFC8" strokeWidth="1" />
              <text x={cutoffX} y="22" textAnchor="middle" fill="#1F2933" fontSize="10" fontWeight="600">
                Cut-off 09:00
              </text>

              {/* Forecast Line */}
              <polyline fill="none" points={fcPoints} stroke="#2F5D8A" strokeWidth="2.5" strokeLinejoin="round" />

              {/* Actual Line */}
              <polyline fill="none" points={actPoints} stroke="#1F2933" strokeWidth="2.5" strokeLinejoin="round" />

              {/* Active hover crosshair and points */}
              {activeRecord && (
                <g className="pointer-events-none">
                  <line x1={activeX} x2={activeX} y1="20" y2="280" stroke="#2F5D8A" strokeWidth="1.5" strokeDasharray="3 3" />
                  <circle cx={activeX} cy={activeFcY} r="4.5" fill="#2F5D8A" stroke="#FFFFFF" strokeWidth="1.5" />
                  <circle cx={activeX} cy={activeActY} r="4.5" fill="#1F2933" stroke="#FFFFFF" strokeWidth="1.5" />

                  {/* Tooltip Box */}
                  <g transform={`translate(${Math.min(activeX + 10, 800)}, 45)`}>
                    <rect width="180" height="90" rx="6" fill="#FFFFFF" stroke="#CFCFC8" strokeWidth="1" filter="drop-shadow(0 2px 4px rgba(31,41,51,0.06))" />
                    <text x="12" y="18" fill="#1F2933" fontSize="11" fontWeight="600">
                      SP {activeRecord.period} · {activeRecord.start_time} - {activeRecord.end_time}
                    </text>
                    <text x="12" y="32" fill="#5F6B76" fontSize="9.5">
                      Horizon: {activeRecord.horizon_hours?.toFixed(1)}h from D-1 08:00
                    </text>
                    <line x1="12" x2="168" y1="38" y2="38" stroke="#E5E5E0" strokeWidth="0.75" />
                    <circle cx="16" cy="49" r="3" fill="#2F5D8A" />
                    <text x="24" y="52" fill="#5F6B76" fontSize="10.5">Forecast (Lock):</text>
                    <text x="168" y="52" textAnchor="end" fill="#1F2933" fontSize="10.5" fontWeight="600" className="font-code">
                      {activeRecord.forecast_mw.toLocaleString()} MW
                    </text>

                    <circle cx="16" cy="65" r="3" fill="#1F2933" />
                    <text x="24" y="68" fill="#5F6B76" fontSize="10.5">Actual Outturn:</text>
                    <text x="168" y="68" textAnchor="end" fill="#1F2933" fontSize="10.5" fontWeight="600" className="font-code">
                      {activeRecord.actual_mw?.toLocaleString() ?? '-'} MW
                    </text>

                    <text
                      x="12"
                      y="83"
                      fill={activeRecord.is_shortfall ? '#9A4311' : '#2E7D6B'}
                      fontSize="10"
                      fontWeight="600"
                    >
                      {activeRecord.is_shortfall ? 'Shortfall: ' : 'Surplus: '}
                      {activeRecord.error_mw != null ? `${activeRecord.error_mw} MW` : ''} ({activeRecord.error_pct}%)
                    </text>
                  </g>
                </g>
              )}

              {/* Hover targets */}
              {records.map((r) => {
                const x = xStart + (r.period - 1) * dx - dx / 2;
                return (
                  <rect
                    key={r.period}
                    x={x}
                    y="20"
                    width={dx}
                    height="260"
                    fill="transparent"
                    className="cursor-pointer"
                    onMouseEnter={() => {
                      setHoveredSP(r.period);
                      onPeriodSelect?.(r.period);
                    }}
                  />
                );
              })}
            </svg>

            {/* Error Sub-Chart (Bars per settlement period) */}
            <div className="mt-2 pt-3 border-t border-border">
              <div className="flex items-center justify-between mb-2">
                <span className="font-label text-label text-text-muted">
                  Settlement Delta / Error Bar (Actual − Forecast in MW)
                </span>
                <span className="font-caption text-caption text-text-muted">
                  Shortfall (&lt;0) vs Surplus (&gt;0)
                </span>
              </div>

              <svg className="w-full h-auto select-none font-caption" viewBox="0 0 1000 110" style={{ display: 'block' }}>
                <line x1="55" x2="980" y1="15" y2="15" stroke="#E5E5E0" strokeDasharray="2 2" strokeWidth="1" />
                <line x1="55" x2="980" y1={errYZero} y2={errYZero} stroke="#1F2933" strokeWidth="1.2" />
                <line x1="55" x2="980" y1="95" y2="95" stroke="#E5E5E0" strokeDasharray="2 2" strokeWidth="1" />

                <text x="48" y="18" textAnchor="end" className="fill-[#5F6B76] font-code text-[9px]">+1,000</text>
                <text x="48" y="58" textAnchor="end" className="fill-[#5F6B76] font-code text-[9px]">0 MW</text>
                <text x="48" y="98" textAnchor="end" className="fill-[#5F6B76] font-code text-[9px]">-1,000</text>

                {records.map((r) => {
                  const x = xStart + (r.period - 1) * dx - 5;
                  const err = r.error_mw ?? 0;
                  const barH = Math.min(Math.abs(err) * errScale, 40);
                  const barY = err >= 0 ? errYZero - barH : errYZero;
                  const isShort = err < 0;

                  return (
                    <rect
                      key={r.period}
                      x={x}
                      y={barY}
                      width="10"
                      height={Math.max(barH, 2)}
                      rx="1"
                      fill={isShort ? '#C2571A' : '#2E7D6B'}
                      stroke={r.period === hoveredSP ? '#1F2933' : undefined}
                      strokeWidth={r.period === hoveredSP ? '1' : undefined}
                      className="cursor-pointer transition-all"
                      onMouseEnter={() => {
                        setHoveredSP(r.period);
                        onPeriodSelect?.(r.period);
                      }}
                    />
                  );
                })}
              </svg>
            </div>
          </div>
        </div>
      </div>

      {/* Chart B: Forecast Vintages Evolution */}
      <div className="bg-surface border border-border rounded-xl p-5">
        <div className="flex flex-col md:flex-row md:items-start justify-between gap-4 pb-4 border-b border-border">
          <div>
            <div className="flex items-center gap-2">
              <h2 className="font-h3 text-h3 text-text">
                Forecast Vintages Evolution &amp; Horizon Drift
              </h2>
              <span className="px-2 py-0.5 rounded text-caption font-caption bg-surface-subtle border border-border text-text-muted">
                BMRS Run History
              </span>
            </div>
            <p className="font-body-sm text-body-sm text-text-muted mt-0.5">
              Comparison of successive BMRS forecast runs published from D-2 through gate closure against final outturn.
            </p>
          </div>
          <div className="flex items-center gap-2 text-caption font-caption">
            <span className="text-text-muted">Selected Target Run:</span>
            <span className="font-code text-code font-medium bg-surface-subtle px-2 py-1 rounded border border-border text-accent-700">
              D-1 08:00 Run (09:00 Lock)
            </span>
          </div>
        </div>

        {/* Vintages Legend */}
        <div className="py-3 flex flex-wrap items-center gap-y-2 gap-x-6 font-caption text-caption border-b border-border bg-surface-subtle/50 px-3 my-3 rounded">
          <div className="flex items-center gap-2">
            <span className="w-4 h-0.5 bg-[#2F5D8A] inline-block" />
            <span className="text-text font-medium">Selected Usable Run (D-1 08:00 locked at 09:00 cut-off)</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-4 h-0.5 bg-[#B8BEC4] inline-block" />
            <span className="text-text-muted">Earlier usable vintages (D-2 17:00, D-1 02:00, D-1 05:00)</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-4 border-b border-dashed border-[#B8BEC4] inline-block" />
            <span className="text-text-muted">Post-Cutoff runs (D-1 14:00) · Excluded</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-4 h-0.5 bg-[#1F2933] inline-block" />
            <span className="text-text font-medium">Outturn Actual</span>
          </div>
        </div>

        {/* Vintages Plot */}
        <div className="overflow-x-auto pt-2">
          <div className="min-w-[840px] w-full">
            <svg className="w-full h-auto select-none font-caption" viewBox="0 0 1000 220" style={{ display: 'block' }}>
              {/* Gridlines */}
              {[
                { mw: 14000, label: '14 GW', y: 20 },
                { mw: 10000, label: '10 GW', y: 75 },
                { mw: 6000, label: '6 GW', y: 130 },
                { mw: 2000, label: '2 GW', y: 185 },
              ].map((g) => (
                <g key={g.mw}>
                  <line x1="55" x2="980" y1={g.y} y2={g.y} stroke="#E5E5E0" strokeWidth="1" strokeDasharray="2 2" />
                  <text x="48" y={g.y + 4} textAnchor="end" className="fill-[#5F6B76] font-code text-[10px]">
                    {g.label}
                  </text>
                </g>
              ))}

              {/* Vertical time markers */}
              {[
                { time: '00:00', x: 60 },
                { time: '04:00', x: 193 },
                { time: '08:00', x: 345 },
                { time: '12:00', x: 498 },
                { time: '16:00', x: 650 },
                { time: '20:00', x: 803 },
                { time: '24:00', x: 975 },
              ].map((t) => (
                <line key={t.time} x1={t.x} x2={t.x} y1="20" y2="185" stroke="#E5E5E0" strokeWidth="1" strokeDasharray="2 2" />
              ))}

              {/* Cut-off line */}
              <line x1={cutoffX} x2={cutoffX} y1="10" y2="185" stroke="#5F6B76" strokeWidth="1.2" strokeDasharray="3 3" />
              <text x={cutoffX + 4} y="22" fill="#5F6B76" fontSize="9" fontWeight="600">
                Cut-off (09:00)
              </text>

              {/* Vintages lines */}
              {(vintages || []).map((v) => {
                const validPeriods = (v.periods || []).filter(
                  (p) => p && typeof p.period === 'number' && typeof p.forecast_mw === 'number' && !isNaN(p.forecast_mw)
                );
                if (validPeriods.length < 2) return null;

                const points = validPeriods
                  .map((p) => {
                    const x = xStart + (p.period - 1) * dx;
                    const mw = Math.max(0, Math.min(14000, p.forecast_mw));
                    const y = 185 - ((mw - 2000) / 12000) * 165;
                    return `${x.toFixed(1)},${Math.max(10, Math.min(200, y)).toFixed(1)}`;
                  })
                  .join(' ');

                return (
                  <polyline
                    key={v.vintage_id}
                    fill="none"
                    points={points}
                    stroke={
                      v.is_selected_at_cutoff
                        ? '#2F5D8A'
                        : v.is_post_cutoff
                        ? '#B8BEC4'
                        : '#B8BEC4'
                    }
                    strokeWidth={v.is_selected_at_cutoff ? '2.5' : '1.2'}
                    strokeDasharray={v.is_post_cutoff ? '3 3' : undefined}
                    opacity={v.is_selected_at_cutoff ? 1 : 0.8}
                  />
                );
              })}

              {/* Actuals line */}
              <polyline
                fill="none"
                points={(records || [])
                  .map((r) => {
                    const x = xStart + (r.period - 1) * dx;
                    const act = r.actual_mw ?? r.forecast_mw ?? 0;
                    const mw = Math.max(0, Math.min(14000, act));
                    const y = 185 - ((mw - 2000) / 12000) * 165;
                    return `${x.toFixed(1)},${Math.max(10, Math.min(200, y)).toFixed(1)}`;
                  })
                  .join(' ')}
                stroke="#1F2933"
                strokeWidth="2.5"
              />
            </svg>
          </div>
        </div>
      </div>
    </div>
  );
};
