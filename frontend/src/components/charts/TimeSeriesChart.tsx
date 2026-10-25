import React, { useState } from 'react';
import { SettlementPeriodRecord } from '../../api/types';
import { Download, TrendingDown, TrendingUp } from 'lucide-react';

interface TimeSeriesChartProps {
  records: SettlementPeriodRecord[];
  showActuals: boolean;
  onExportCsv?: () => void;
  confidence?: number;
}

export const TimeSeriesChart: React.FC<TimeSeriesChartProps> = ({
  records,
  showActuals,
  onExportCsv,
  confidence = 90,
}) => {
  const [hoveredIdx, setHoveredIdx] = useState<number | null>(27); // default hover on SP 28 (14:00)
  const [viewMode, setViewMode] = useState<'chart' | 'table'>('chart');

  // Chart coordinate mapping
  // X: 55 to 735 (width 680, dx = 680 / 47 = 14.47px per period)
  const xStart = 55;
  const xEnd = 735;
  const widthSpan = xEnd - xStart;
  const count = records.length || 48;
  const dx = widthSpan / (count - 1);

  // Y: 0 to 16,000 MW. Baseline y=290 (0 MW), Top y=30 (16,000 MW). Height = 260px.
  // 1 MW = 260 / 16000 = 0.01625 px.
  const yBase = 290;
  const maxMw = 16000;
  const scaleY = (mw: number) => yBase - (mw / maxMw) * 260;

  // Build SVG points for forecast
  const forecastPoints = records.map((r, i) => {
    const x = xStart + i * dx;
    const y = scaleY(r.forecast_mw);
    return `${x},${y}`;
  });

  // Build SVG points for actuals
  const actualPoints = records.map((r, i) => {
    const x = xStart + i * dx;
    const act = r.actual_mw ?? r.forecast_mw;
    const y = scaleY(act);
    return `${x},${y}`;
  });

  // Build P90 Buffer band polygon
  // Band runs from forecast down to (forecast - buffer)
  const bufferPointsTop = records.map((r, i) => {
    const x = xStart + i * dx;
    const y = scaleY(r.forecast_mw);
    return `${x},${y}`;
  });

  const bufferPointsBottom = records
    .slice()
    .reverse()
    .map((r, i) => {
      const origIdx = records.length - 1 - i;
      const x = xStart + origIdx * dx;
      const buffer = r.buffer_p90_mw || 410;
      const y = scaleY(Math.max(0, r.forecast_mw - buffer));
      return `${x},${y}`;
    });

  const bufferPathString = `M ${bufferPointsTop.join(' L ')} L ${bufferPointsBottom.join(' L ')} Z`;

  // Cut-off line at 09:00 London (Period 18: idx 17)
  const cutoffIdx = 17;
  const cutoffX = xStart + cutoffIdx * dx;

  // Hovered record
  const currentRecord = hoveredIdx != null ? records[hoveredIdx] : null;
  const hoverX = hoveredIdx != null ? xStart + hoveredIdx * dx : 0;
  const hoverForecastY = currentRecord ? scaleY(currentRecord.forecast_mw) : 0;
  const hoverActualY = currentRecord && currentRecord.actual_mw != null ? scaleY(currentRecord.actual_mw) : 0;

  return (
    <div className="bg-surface border border-border rounded-xl p-5 flex flex-col justify-between">
      {/* Chart Header & Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-border">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="font-h3 text-h3 text-text">
              Day-ahead wind forecast &amp; risk band
            </h2>
            <span className="px-2 py-0.5 rounded text-[11px] font-code font-medium bg-surface-subtle text-text-muted border border-border">
              48 SPs
            </span>
          </div>
          <p className="font-body-sm text-body-sm text-text-muted mt-0.5">
            Half-hourly power (MW) across 48 settlement periods · 16 Jan 2026
          </p>
        </div>

        <div className="flex items-center gap-2">
          {/* Segmented Chart / Table toggle */}
          <div className="flex items-center bg-surface-subtle border border-border rounded p-0.5">
            <button
              type="button"
              onClick={() => setViewMode('chart')}
              className={`px-2.5 py-1 text-label font-label rounded-sm transition-all ${
                viewMode === 'chart'
                  ? 'bg-surface text-text font-semibold shadow-none'
                  : 'text-text-muted hover:text-text'
              }`}
            >
              Chart
            </button>
            <button
              type="button"
              onClick={() => setViewMode('table')}
              className={`px-2.5 py-1 text-label font-label rounded-sm transition-all ${
                viewMode === 'table'
                  ? 'bg-surface text-text font-semibold shadow-none'
                  : 'text-text-muted hover:text-text'
              }`}
            >
              Table
            </button>
          </div>

          {onExportCsv && (
            <button
              type="button"
              onClick={onExportCsv}
              className="h-8 w-8 flex items-center justify-center bg-surface border border-border rounded text-text-muted hover:text-text hover:bg-surface-subtle transition-colors"
              title="Download Series CSV"
            >
              <Download className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      {/* Legend Indicators */}
      <div className="flex flex-wrap items-center gap-x-5 gap-y-2 py-3 text-body-sm font-body-sm">
        <div className="flex items-center gap-2">
          <span className="w-3.5 h-0.5 bg-data-forecast rounded-full" />
          <span className="text-text font-medium">Forecast (09:00 lock)</span>
        </div>

        <div className="flex items-center gap-2">
          <span className="w-3.5 h-2 bg-data-buffer-band border border-accent-500/30 rounded-xs" />
          <span className="text-text-muted">{confidence}% Risk Buffer (P{confidence})</span>
        </div>

        {showActuals && (
          <div className="flex items-center gap-2">
            <span className="w-3.5 h-0.5 bg-data-actual rounded-full" />
            <span className="text-text font-medium">Actual Outturn</span>
          </div>
        )}

        <div className="flex items-center gap-2">
          <span className="w-3 h-0 border-t border-dashed border-text-muted" />
          <span className="text-caption font-caption text-text-muted">Cut-off marker</span>
        </div>
      </div>

      {viewMode === 'chart' ? (
        <div className="relative w-full aspect-[16/9] min-h-[300px] mt-1 select-none">
          <svg
            className="w-full h-full overflow-visible"
            viewBox="0 0 760 340"
            preserveAspectRatio="none"
            onMouseLeave={() => setHoveredIdx(27)}
          >
            <defs>
              <linearGradient id="bufferGradient" x1="0" x2="0" y1="0" y2="1">
                <stop offset="0%" stopColor="#2F5D8A" stopOpacity="0.22" />
                <stop offset="100%" stopColor="#2F5D8A" stopOpacity="0.04" />
              </linearGradient>
            </defs>

            {/* Horizontal Gridlines & Y-Axis Labels */}
            {[
              { mw: 16000, label: '16k', y: 30 },
              { mw: 12000, label: '12k', y: 95 },
              { mw: 8000, label: '8k', y: 160 },
              { mw: 4000, label: '4k', y: 225 },
              { mw: 0, label: '0', y: 290 },
            ].map((grid) => (
              <g key={grid.mw}>
                <line
                  x1="50"
                  x2="740"
                  y1={grid.y}
                  y2={grid.y}
                  stroke={grid.mw === 0 ? '#CFCFC8' : '#E5E5E0'}
                  strokeWidth="1"
                />
                <text
                  x="42"
                  y={grid.y + 4}
                  textAnchor="end"
                  className="font-code text-[11px] fill-[#5F6B76]"
                >
                  {grid.label}
                </text>
              </g>
            ))}

            {/* Vertical Time Axis Ticks and Labels */}
            {[
              { sp: 1, label: '00:00', x: 55 },
              { sp: 9, label: '04:00', x: 169 },
              { sp: 17, label: '08:00', x: 283 },
              { sp: 25, label: '12:00', x: 397 },
              { sp: 33, label: '16:00', x: 511 },
              { sp: 41, label: '20:00', x: 625 },
              { sp: 48, label: '24:00', x: 735 },
            ].map((t) => (
              <g key={t.sp}>
                <line x1={t.x} x2={t.x} y1="290" y2="295" stroke="#CFCFC8" strokeWidth="1" />
                <text
                  x={t.x}
                  y="310"
                  textAnchor="middle"
                  className="font-code text-[11px] fill-[#5F6B76]"
                >
                  {t.label}
                </text>
              </g>
            ))}

            {/* Cut-off Vertical Reference Line (09:00 London) */}
            <g className="pointer-events-none">
              <line
                x1={cutoffX}
                x2={cutoffX}
                y1="20"
                y2="290"
                stroke="#5F6B76"
                strokeWidth="1.5"
                strokeDasharray="4 4"
              />
              <rect
                x={cutoffX - 42}
                y="8"
                width="84"
                height="18"
                rx="4"
                fill="#F4F4EF"
                stroke="#CFCFC8"
                strokeWidth="1"
              />
              <text
                x={cutoffX}
                y="21"
                textAnchor="middle"
                className="font-code text-[10px] fill-[#1F2933] font-medium"
              >
                Cut-off 09:00
              </text>
            </g>

            {/* Risk Buffer Band (P90) Area */}
            <path d={bufferPathString} fill="url(#bufferGradient)" stroke="none" />

            {/* Forecast Line (#2F5D8A) */}
            <path
              d={`M ${forecastPoints.join(' L ')}`}
              fill="none"
              stroke="#2F5D8A"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />

            {/* Actuals Line (#1F2933) */}
            {showActuals && (
              <path
                d={`M ${actualPoints.join(' L ')}`}
                fill="none"
                stroke="#1F2933"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            )}

            {/* Interactive Hover Guides & Crosshair */}
            {hoveredIdx != null && (
              <g className="pointer-events-none">
                <line
                  x1={hoverX}
                  x2={hoverX}
                  y1="30"
                  y2="290"
                  stroke="#2F5D8A"
                  strokeWidth="1"
                  strokeDasharray="2 2"
                  opacity="0.6"
                />
                <circle cx={hoverX} cy={hoverForecastY} r="4.5" fill="#2F5D8A" stroke="#FFFFFF" strokeWidth="2" />
                {showActuals && (
                  <circle cx={hoverX} cy={hoverActualY} r="4" fill="#1F2933" stroke="#FFFFFF" strokeWidth="1.5" />
                )}
              </g>
            )}

            {/* Transparent hover capture rects for all 48 settlement periods */}
            {records.map((r, i) => {
              const x = xStart + i * dx - dx / 2;
              return (
                <rect
                  key={r.period}
                  x={x}
                  y="20"
                  width={dx}
                  height="270"
                  fill="transparent"
                  className="cursor-pointer"
                  onMouseEnter={() => setHoveredIdx(i)}
                />
              );
            })}
          </svg>

          {/* Interactive Floating Tooltip Overlay */}
          {currentRecord && (
            <div
              className="absolute z-20 bg-surface border border-border-strong rounded-lg p-3 pointer-events-none w-64 shadow-1 animate-fade-in"
              style={{
                left: `${Math.min(Math.max((hoverX / 760) * 100, 20), 80)}%`,
                top: '15%',
                transform: 'translateX(-50%)',
              }}
            >
              <div className="flex items-center justify-between pb-1.5 border-b border-border text-caption font-caption">
                <span className="font-code font-semibold text-text">
                  SP {String(currentRecord.period).padStart(2, '0')} · {currentRecord.start_time} UTC
                </span>
                <span className="text-text-muted">Settlement</span>
              </div>

              <div className="mt-2 space-y-1.5 font-code text-caption">
                <div className="flex items-center justify-between">
                  <span className="text-text-muted flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-data-forecast" />
                    Forecast:
                  </span>
                  <span className="font-semibold text-text tabular-nums">
                    {currentRecord.forecast_mw.toLocaleString()} MW
                  </span>
                </div>

                {showActuals && currentRecord.actual_mw != null && (
                  <div className="flex items-center justify-between">
                    <span className="text-text-muted flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-data-actual" />
                      Actual:
                    </span>
                    <span className="font-semibold text-text tabular-nums">
                      {currentRecord.actual_mw.toLocaleString()} MW
                    </span>
                  </div>
                )}

                {showActuals && currentRecord.error_mw != null && (
                  <div className="flex items-center justify-between pt-1 border-t border-border">
                    <span className="text-text-muted flex items-center gap-1.5">
                      {currentRecord.is_shortfall ? (
                        <TrendingDown className="w-3.5 h-3.5 text-data-shortfall" />
                      ) : (
                        <TrendingUp className="w-3.5 h-3.5 text-success" />
                      )}
                      Variance:
                    </span>
                    <span
                      className={`font-semibold tabular-nums ${
                        currentRecord.is_shortfall ? 'text-data-shortfall-text' : 'text-success'
                      }`}
                    >
                      {currentRecord.error_mw > 0 ? `+${currentRecord.error_mw}` : currentRecord.error_mw} MW{' '}
                      {currentRecord.is_shortfall ? 'shortfall' : 'surplus'}
                    </span>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      ) : (
        /* Alternative Table View */
        <div className="max-h-80 overflow-y-auto mt-2 border border-border rounded-lg">
          <table className="w-full text-left text-body-sm">
            <thead className="bg-surface-subtle sticky top-0 border-b border-border text-caption font-label text-text-muted uppercase">
              <tr>
                <th className="py-2 px-3">Period</th>
                <th className="py-2 px-3">Time</th>
                <th className="py-2 px-3 text-right">Forecast (MW)</th>
                {showActuals && <th className="py-2 px-3 text-right">Actual (MW)</th>}
                {showActuals && <th className="py-2 px-3 text-right">Error (MW)</th>}
                <th className="py-2 px-3 text-right">Buffer (MW)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {records.map((r) => (
                <tr key={r.period} className="hover:bg-surface-subtle transition-colors">
                  <td className="py-2 px-3 font-code">{r.period}</td>
                  <td className="py-2 px-3 font-code">{r.start_time}</td>
                  <td className="py-2 px-3 text-right font-code font-medium">{r.forecast_mw.toLocaleString()}</td>
                  {showActuals && (
                    <td className="py-2 px-3 text-right font-code">{r.actual_mw?.toLocaleString() ?? '-'}</td>
                  )}
                  {showActuals && (
                    <td
                      className={`py-2 px-3 text-right font-code font-semibold ${
                        r.is_shortfall ? 'text-data-shortfall-text' : 'text-success'
                      }`}
                    >
                      {r.error_mw != null ? (r.error_mw > 0 ? `+${r.error_mw}` : r.error_mw) : '-'}
                    </td>
                  )}
                  <td className="py-2 px-3 text-right font-code text-text-muted">{r.buffer_p90_mw ?? 410}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Settlement Period Quick Range Scrub */}
      <div className="mt-3 pt-3 border-t border-border flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-caption font-caption text-text-muted">
        <div className="flex items-center gap-4">
          <span>
            Range: <strong>SP 01 (00:00)</strong> to <strong>SP 48 (23:30)</strong>
          </span>
          <span className="hidden md:inline text-border-strong">·</span>
          <span className="hidden md:inline">
            Peak gradient: <strong>+1,420 MW/h</strong> (SP 16–19)
          </span>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-data-shortfall font-medium">Shortfall episodes: 2 periods</span>
          <span className="text-border-strong">·</span>
          <span className="text-success font-medium">Surplus episodes: 5 periods</span>
        </div>
      </div>
    </div>
  );
};
