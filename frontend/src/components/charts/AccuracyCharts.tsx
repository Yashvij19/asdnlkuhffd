import React, { useState } from 'react';
import { DailyAccuracyRecord, DistributionResult, HorizonDegradationRecord, HourlyErrorRecord } from '../../api/types';

// 1. Daily MAE & Signed Bias Chart
export const DailyMaeBiasChart: React.FC<{
  data: DailyAccuracyRecord[];
  onSelectDate?: (date: string) => void;
}> = ({ data, onSelectDate }) => {
  const [hoveredDate, setHoveredDate] = useState<string | null>('2026-01-16');

  // Guard against empty data
  const safeData = data.length > 0 ? data : [];
  const count = safeData.length || 31;

  // Dynamic scaling for MAE bars
  const maxDataMae = Math.max(...safeData.map((d) => d.mae_mw || 0), 1200);
  const yAxisMaxMae = Math.ceil(maxDataMae / 500) * 500;

  // Coordinate geometry
  const xStart = 55;
  const xEnd = 725;
  const dx = (xEnd - xStart) / Math.max(count - 1, 1);
  const barWidth = Math.max(8, Math.min(16, dx * 0.7));

  // Chart baseline is at y=250. Top is at y=35. Usable height is 215px.
  const yBase = 250;
  const chartHeight = 210;
  const scaleMae = (mae: number) => Math.max(3, (Math.min(mae, yAxisMaxMae) / yAxisMaxMae) * chartHeight);

  // Dynamic scaling for Bias curve:
  // Zero line is positioned at y=150. Max positive bias at y=45, max negative bias at y=245.
  const maxAbsBias = Math.max(...safeData.map((d) => Math.abs(d.bias_mw || 0)), 600);
  const yAxisMaxBias = Math.ceil(maxAbsBias / 500) * 500;
  const zeroBiasY = 160;
  const biasSpan = 100;

  const scaleBiasY = (bias: number) => {
    const norm = (bias / yAxisMaxBias) * biasSpan;
    const computedY = zeroBiasY - norm;
    // Strictly clamp within SVG area so lines never spike off canvas
    return Math.max(38, Math.min(242, computedY));
  };

  const biasPoints = safeData
    .map((d, i) => `${(xStart + i * dx + barWidth / 2).toFixed(1)},${scaleBiasY(d.bias_mw).toFixed(1)}`)
    .join(' L ');

  const hoveredItem =
    safeData.find((d) => d.date === hoveredDate) ||
    safeData.find((d) => d.date === '2026-01-16') ||
    safeData[Math.floor(safeData.length / 2)] ||
    null;

  // Dynamic step lines
  const stepCount = 4;
  const guides = Array.from({ length: stepCount + 1 }, (_, idx) => {
    const fraction = (stepCount - idx) / stepCount;
    const mwVal = Math.round(yAxisMaxMae * fraction);
    const yPos = 35 + chartHeight * (1 - fraction);
    return {
      label: mwVal === 0 ? '0 MW' : `${mwVal.toLocaleString()}`,
      y: yPos,
      isZero: mwVal === 0,
    };
  });

  return (
    <div className="bg-surface border border-border rounded-xl p-5 sm:p-6 flex flex-col justify-between">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-border">
        <div>
          <h3 className="font-h3 text-h3 text-text">Daily MAE and Directional Bias</h3>
          <p className="font-caption text-caption text-text-muted mt-0.5">
            Mean absolute error bars paired with signed bias curve across Jan 2026 delivery days
          </p>
        </div>

        {/* Legend */}
        <div className="flex flex-wrap items-center gap-4 font-caption text-caption text-text-muted">
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded-xs bg-accent-200" />
            <span>Daily MAE (MW)</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-3.5 h-0.5 bg-accent-600 rounded-full" />
            <span>Forecast Bias (MW)</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-3.5 h-0.5 border-t border-dashed border-text-muted" />
            <span>Zero Baseline</span>
          </div>
        </div>
      </div>

      {/* SVG Canvas */}
      <div className="relative w-full h-[320px] mt-4 select-none">
        <svg className="w-full h-full" viewBox="0 0 760 300" preserveAspectRatio="none">
          <defs>
            <linearGradient id="maeBarGradient" x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stopColor="#2F5D8A" stopOpacity="0.8" />
              <stop offset="100%" stopColor="#B3CBE0" stopOpacity="0.4" />
            </linearGradient>
            <linearGradient id="stormGerritGradient" x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stopColor="#C2571A" stopOpacity="0.9" />
              <stop offset="100%" stopColor="#FBD5B5" stopOpacity="0.5" />
            </linearGradient>
          </defs>

          {/* Guides & Gridlines */}
          {guides.map((g) => (
            <g key={g.y}>
              <line
                x1="45"
                x2="745"
                y1={g.y}
                y2={g.y}
                stroke={g.isZero ? '#CFCFC8' : '#E5E5E0'}
                strokeWidth={g.isZero ? '1.5' : '1'}
                strokeDasharray={g.isZero ? '4 3' : '2 2'}
              />
              <text
                x="38"
                y={g.y + 4}
                textAnchor="end"
                className={`font-code text-[10px] ${g.isZero ? 'fill-text font-semibold' : 'fill-text-muted'}`}
              >
                {g.label}
              </text>
            </g>
          ))}

          {/* Zero Bias Baseline (Reference dotted line) */}
          <line
            x1="45"
            x2="745"
            y1={zeroBiasY}
            y2={zeroBiasY}
            stroke="#9AA3AB"
            strokeWidth="1"
            strokeDasharray="2 3"
          />

          {/* Daily MAE Bars */}
          {safeData.map((d, i) => {
            const x = xStart + i * dx;
            const h = scaleMae(d.mae_mw);
            const y = yBase - h;
            const isStormGerrit = d.date === '2026-01-18';
            const isSelected = d.date === hoveredItem?.date;

            return (
              <rect
                key={d.date || i}
                x={x}
                y={y}
                width={barWidth}
                height={h}
                rx="2"
                fill={isStormGerrit ? 'url(#stormGerritGradient)' : isSelected ? '#2F5D8A' : 'url(#maeBarGradient)'}
                stroke={isSelected ? '#104571' : isStormGerrit ? '#9A4311' : undefined}
                strokeWidth={isSelected || isStormGerrit ? '1.5' : undefined}
                className="cursor-pointer transition-colors"
                onMouseEnter={() => setHoveredDate(d.date)}
                onClick={() => onSelectDate?.(d.date)}
              />
            );
          })}

          {/* Signed Bias Line */}
          {biasPoints && (
            <path
              d={`M ${biasPoints}`}
              fill="none"
              stroke="#104571"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          )}

          {/* Hovered point marker */}
          {hoveredItem && (
            <circle
              cx={xStart + safeData.indexOf(hoveredItem) * dx + barWidth / 2}
              cy={scaleBiasY(hoveredItem.bias_mw)}
              r="4.5"
              fill="#FFFFFF"
              stroke="#104571"
              strokeWidth="2.5"
            />
          )}

          {/* X Axis Date Labels */}
          {safeData.map((d, i) => {
            if (i % 5 !== 0 && i !== safeData.length - 1) return null;
            const dayLabel = d.date ? d.date.slice(8, 10) : String(i + 1).padStart(2, '0');
            return (
              <text
                key={d.date || i}
                x={xStart + i * dx + barWidth / 2}
                y="275"
                textAnchor="middle"
                className="fill-[#5F6B76] font-code text-[10px]"
              >
                {dayLabel}
              </text>
            );
          })}
        </svg>

        {/* Hover / Tooltip callout */}
        {hoveredItem && (
          <div
            className="absolute z-10 bg-surface/95 border border-border-strong rounded-lg p-2.5 shadow-md text-caption pointer-events-none"
            style={{
              left: `${Math.min(
                Math.max(((safeData.indexOf(hoveredItem) * dx + 55) / 760) * 100, 15),
                82
              )}%`,
              top: '12%',
              transform: 'translateX(-50%)',
            }}
          >
            <div className="font-label text-text font-semibold">{hoveredItem.date}</div>
            <div className="font-code text-accent-700 font-medium">
              MAE: {hoveredItem.mae_mw.toLocaleString()} MW
            </div>
            <div className="font-code text-text-muted">
              Bias:{' '}
              <span className={hoveredItem.bias_mw < 0 ? 'text-data-shortfall-text font-medium' : 'text-success font-medium'}>
                {hoveredItem.bias_mw >= 0 ? `+${hoveredItem.bias_mw.toLocaleString()}` : `${hoveredItem.bias_mw.toLocaleString()}`} MW
              </span>
            </div>
            {hoveredItem.date === '2026-01-18' && (
              <div className="font-caption text-data-shortfall font-medium mt-0.5">
                Storm Gerrit Outlier
              </div>
            )}
          </div>
        )}
      </div>

      <div className="pt-3 border-t border-border flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-text-muted font-caption text-caption">
        <span>Target operating tolerance band: MAE &lt; 640 MW</span>
        <span className="text-data-shortfall font-medium">18 Jan (Storm Gerrit): Outlier day MAE 1,124 MW</span>
      </div>
    </div>
  );
};

// 2. Forecast vs Actual 45° Correlation Scatter Plot
export const ScatterChart: React.FC = () => {
  return (
    <div className="bg-surface border border-border rounded-xl p-5 flex flex-col justify-between">
      <div className="pb-3 border-b border-border">
        <div className="flex items-center justify-between">
          <h3 className="font-h3 text-h3 text-text">Forecast vs Actual</h3>
          <span className="px-2 py-0.5 rounded bg-surface-subtle border border-border font-caption text-caption text-text font-medium">
            r = 0.94
          </span>
        </div>
        <p className="font-caption text-caption text-text-muted mt-0.5">
          1,488 SPs plotted against 45° ideal equality line
        </p>
      </div>

      {/* SVG Scatter Plot */}
      <div className="relative w-full aspect-square my-3 select-none flex items-center justify-center">
        <svg className="w-full h-full" viewBox="0 0 280 280">
          {/* Shortfall Shaded Zone (Under 45-degree diagonal) */}
          <polygon fill="rgba(194, 87, 26, 0.05)" points="35,245 255,25 255,245" />

          {/* Subtle Grid lines */}
          <line x1="35" x2="255" y1="245" y2="245" stroke="#E5E5E0" strokeWidth="1" />
          <line x1="35" x2="255" y1="190" y2="190" stroke="#E5E5E0" strokeDasharray="2 2" strokeWidth="1" />
          <line x1="35" x2="255" y1="135" y2="135" stroke="#E5E5E0" strokeDasharray="2 2" strokeWidth="1" />
          <line x1="35" x2="255" y1="80" y2="80" stroke="#E5E5E0" strokeDasharray="2 2" strokeWidth="1" />
          <line x1="35" x2="255" y1="25" y2="25" stroke="#E5E5E0" strokeDasharray="2 2" strokeWidth="1" />

          <line x1="35" x2="35" y1="245" y2="25" stroke="#E5E5E0" strokeWidth="1" />
          <line x1="90" x2="90" y1="245" y2="25" stroke="#E5E5E0" strokeDasharray="2 2" strokeWidth="1" />
          <line x1="145" x2="145" y1="245" y2="25" stroke="#E5E5E0" strokeDasharray="2 2" strokeWidth="1" />
          <line x1="200" x2="200" y1="245" y2="25" stroke="#E5E5E0" strokeDasharray="2 2" strokeWidth="1" />
          <line x1="255" x2="255" y1="245" y2="25" stroke="#E5E5E0" strokeDasharray="2 2" strokeWidth="1" />

          {/* 45° Equality Line */}
          <line x1="35" x2="255" y1="245" y2="25" stroke="#CFCFC8" strokeDasharray="4 3" strokeWidth="1.5" />

          {/* Representative Sample Dots */}
          <g fill="#2F5D8A" fillOpacity="0.45">
            {/* Low band */}
            {[
              [48, 230], [52, 225], [58, 220], [65, 215], [68, 208], [72, 210],
              [78, 200], [82, 195], [86, 192],
              /* Mid band */
              [95, 182], [102, 178], [106, 170], [112, 168], [118, 160], [122, 155],
              [128, 158], [134, 148], [138, 142], [144, 138], [148, 130], [152, 128],
              [158, 122], [162, 118], [166, 115], [170, 112], [175, 105], [180, 102],
              /* High band */
              [188, 98], [192, 90], [195, 85], [202, 80], [206, 74], [210, 82],
              [215, 68], [220, 62], [225, 58], [230, 50], [236, 45], [242, 40],
            ].map(([cx, cy], i) => (
              <circle key={i} cx={cx} cy={cy} r="2.2" />
            ))}

            {/* Outliers */}
            <circle cx="140" cy="175" r="2.5" fill="#C2571A" fillOpacity="0.8" />
            <circle cx="175" cy="135" r="2.5" fill="#C2571A" fillOpacity="0.8" />
            <circle cx="210" cy="115" r="3" fill="#C2571A" fillOpacity="0.9" />
            <circle cx="225" cy="92" r="2.5" fill="#C2571A" fillOpacity="0.8" />
          </g>

          {/* Text Labels */}
          <text x="190" y="150" className="font-caption fill-[#9A4311] text-[9px] font-medium">
            Shortfall Zone (Actual &lt; Fcst)
          </text>
          <text x="40" y="50" className="font-caption fill-text-muted text-[9px]">
            Surplus Zone
          </text>
          <text x="210" y="30" className="font-caption fill-text-muted text-[9px]">
            45° Parity
          </text>

          {/* Axes */}
          <text x="35" y="258" textAnchor="middle" className="font-caption fill-text-muted text-[9px]">0</text>
          <text x="145" y="258" textAnchor="middle" className="font-caption fill-text-muted text-[9px]">8 GW</text>
          <text x="255" y="258" textAnchor="middle" className="font-caption fill-text-muted text-[9px]">16 GW</text>
          <text x="145" y="272" textAnchor="middle" className="font-caption fill-text font-medium text-[10px]">
            Forecast Volume (MW)
          </text>

          <text x="28" y="248" textAnchor="end" className="font-caption fill-text-muted text-[9px]">0</text>
          <text x="28" y="138" textAnchor="end" className="font-caption fill-text-muted text-[9px]">8 GW</text>
          <text x="28" y="28" textAnchor="end" className="font-caption fill-text-muted text-[9px]">16 GW</text>
        </svg>
      </div>

      <div className="pt-3 border-t border-border flex items-center justify-between text-text-muted font-caption text-caption">
        <span>High correlation (R² = 0.88)</span>
        <span className="text-text font-medium">Increased dispersion &gt; 10 GW</span>
      </div>
    </div>
  );
};

// 3. Hourly Diurnal Error Profile (Deep-Dive)
export const HourlyErrorChart: React.FC<{ data: HourlyErrorRecord[] }> = ({ data }) => {
  const [hoveredHour, setHoveredHour] = useState<number | null>(19); // default 19:00 evening peak

  // 24 hours: x from 58 to 725 (span 667, dx = 667 / 23 = 29px)
  const xStart = 58;
  const dx = 29;
  const barWidth = 18;

  // Max MAE 900 MW. Base at y=270, height scales to MAE.
  const scaleMae = (mae: number) => (mae / 900) * 230;

  // Zero baseline for Bias is at y=170. +800 MW at y=25, -600 MW at y=270.
  const scaleBiasY = (bias: number) => 170 - (bias / 800) * 145;

  const biasPoints = data
    .map((d, i) => `${xStart + i * dx + barWidth / 2},${scaleBiasY(d.bias_mw)}`)
    .join(' L ');

  const currentItem = hoveredHour != null ? data[hoveredHour] : data[19];

  return (
    <div className="bg-surface border border-border rounded-xl p-5 flex flex-col gap-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h2 className="font-h3 text-h3 text-text tracking-tight">
            Hourly Error Profile: MAE &amp; Directional Bias across Diurnal Cycle
          </h2>
          <p className="font-body-sm text-caption text-text-muted mt-0.5">
            Half-hourly MAE bars paired with signed bias curve across 24 hours (London time)
          </p>
        </div>
      </div>

      {/* Legend */}
      <div className="flex flex-wrap items-center gap-4 text-caption text-text-muted pt-1">
        <div className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-sm bg-accent-200" />
          <span>MAE (MW)</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-4 h-0.5 bg-accent-500" />
          <span>Signed Bias (MW)</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-4 h-0 border-t border-dashed border-border-strong" />
          <span>Zero Baseline</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-sm bg-data-shortfall/15 border border-data-shortfall/30" />
          <span className="text-data-shortfall-text font-medium">Peak Shortfall Window (16:00–20:00)</span>
        </div>
      </div>

      {/* SVG Canvas */}
      <div className="relative w-full h-[340px] bg-bg/50 border border-border rounded-lg p-3 overflow-hidden select-none">
        <svg className="w-full h-full" viewBox="0 0 760 300" preserveAspectRatio="none">
          {/* Shaded Peak Shortfall Zone (16:00 to 20:00: x=522 to x=638) */}
          <rect x="522" y="20" width="116" height="250" fill="#C2571A" fillOpacity="0.08" />
          <line x1="522" x2="522" y1="20" y2="270" stroke="#C2571A" strokeOpacity="0.3" strokeWidth="1" />
          <line x1="638" x2="638" y1="20" y2="270" stroke="#C2571A" strokeOpacity="0.3" strokeWidth="1" />

          {/* Zero baseline at y=170 */}
          <line x1="50" x2="750" y1="170" y2="170" stroke="#727780" strokeWidth="1.25" />
          <text x="44" y="173" textAnchor="end" className="fill-[#5F6B76] font-body text-[10px]">0</text>
          <text x="44" y="25" textAnchor="end" className="fill-[#5F6B76] font-body text-[10px]">+800</text>
          <text x="44" y="95" textAnchor="end" className="fill-[#5F6B76] font-body text-[10px]">+400</text>
          <text x="44" y="245" textAnchor="end" className="fill-[#C2571A] font-body text-[10px]">-400</text>

          {/* Hourly MAE Bars */}
          {data.map((d, i) => {
            const x = xStart + i * dx;
            const h = scaleMae(d.mae_mw);
            const y = 270 - h;
            const isPeak = d.is_peak_window;

            return (
              <rect
                key={d.hour}
                x={x}
                y={y}
                width={barWidth}
                height={h}
                rx="1"
                fill={isPeak ? '#2F5D8A' : '#B3CBE0'}
                fillOpacity={isPeak ? (d.hour === 19 ? 0.8 : 0.6) : 1}
                className="cursor-pointer transition-all"
                onMouseEnter={() => setHoveredHour(d.hour)}
              />
            );
          })}

          {/* Signed Bias Curve */}
          <path
            d={`M ${biasPoints}`}
            fill="none"
            stroke="#2F5D8A"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />

          {/* 19:00 Peak node */}
          <circle cx={xStart + 19 * dx + barWidth / 2} cy={scaleBiasY(-340)} r="4.5" fill="#C2571A" stroke="#FFFFFF" strokeWidth="2" />

          {/* X Axis Hours */}
          {[0, 4, 8, 12, 16, 19, 23].map((h) => (
            <text
              key={h}
              x={xStart + h * dx + barWidth / 2}
              y="286"
              textAnchor="middle"
              className={`font-body text-[10px] ${h === 19 ? 'fill-[#C2571A] font-semibold' : 'fill-[#5F6B76]'}`}
            >
              {String(h).padStart(2, '0')}:00
            </text>
          ))}
        </svg>

        {/* Hover Popover */}
        {currentItem && (
          <div
            className="absolute z-10 bg-surface/95 border border-border-strong rounded-lg p-2.5 shadow-sm text-caption pointer-events-none"
            style={{
              left: `${Math.min(Math.max(((currentItem.hour * dx + 58) / 760) * 100, 15), 80)}%`,
              top: '15%',
              transform: 'translateX(-50%)',
            }}
          >
            <div className="flex items-center justify-between gap-2 border-b border-border pb-1 mb-1">
              <span className="font-semibold text-text">{currentItem.time_label} London</span>
              {currentItem.is_peak_window && (
                <span className="text-data-shortfall font-semibold text-[10px] uppercase">Peak Ramp</span>
              )}
            </div>
            <div className="flex justify-between gap-4 font-code">
              <span className="text-text-muted">MAE:</span>
              <span className="font-medium text-text">{currentItem.mae_mw} MW</span>
            </div>
            <div className="flex justify-between gap-4 font-code">
              <span className="text-text-muted">Signed Bias:</span>
              <span className="font-medium text-data-shortfall">{currentItem.bias_mw} MW</span>
            </div>
            <div className="flex justify-between gap-4 font-code">
              <span className="text-text-muted">P90 Shortfall:</span>
              <span className="font-bold text-data-shortfall-text">{currentItem.p90_shortfall_mw} MW</span>
            </div>
          </div>
        )}
      </div>

      <div className="flex items-center justify-between text-caption text-text-muted pt-1">
        <span>Aggregate across 1,488 verified Settlement Periods (January 2026 outturn).</span>
        <span className="font-code">London Local Clock (UTC+0)</span>
      </div>
    </div>
  );
};

// 4. Horizon Degradation Chart (0-48h lead time)
export const HorizonDegradationChart: React.FC<{ data: HorizonDegradationRecord[] }> = ({ data }) => {
  return (
    <div className="bg-surface border border-border rounded-xl p-5 flex flex-col gap-3">
      <div className="flex items-start justify-between">
        <div>
          <h3 className="font-h3 text-h3 text-text tracking-tight">Forecast Horizon Degradation</h3>
          <p className="font-body-sm text-caption text-text-muted mt-0.5">
            Error growth as decision lead-time increases from gate closure (0h to 48h horizon)
          </p>
        </div>
        <span className="px-2 py-0.5 rounded text-caption font-code font-medium bg-surface-subtle border border-border text-text-muted">
          +10.4 MW/hr Lead
        </span>
      </div>

      <div className="relative w-full h-[220px] bg-bg/50 border border-border rounded-lg p-3">
        <svg className="w-full h-full" viewBox="0 0 500 180" preserveAspectRatio="none">
          <line x1="40" x2="480" y1="30" y2="30" stroke="#E5E5E0" strokeDasharray="2 2" strokeWidth="1" />
          <line x1="40" x2="480" y1="75" y2="75" stroke="#E5E5E0" strokeDasharray="2 2" strokeWidth="1" />
          <line x1="40" x2="480" y1="120" y2="120" stroke="#E5E5E0" strokeDasharray="2 2" strokeWidth="1" />
          <line x1="40" x2="480" y1="155" y2="155" stroke="#727780" strokeWidth="1" />

          <text x="34" y="34" textAnchor="end" className="fill-[#5F6B76] font-body text-[9px]">800</text>
          <text x="34" y="79" textAnchor="end" className="fill-[#5F6B76] font-body text-[9px]">600</text>
          <text x="34" y="124" textAnchor="end" className="fill-[#5F6B76] font-body text-[9px]">400</text>
          <text x="34" y="158" textAnchor="end" className="fill-[#5F6B76] font-body text-[9px]">200</text>

          {/* 24h Cut-off marker */}
          <line x1="260" x2="260" y1="20" y2="155" stroke="#2F5D8A" strokeDasharray="2 2" strokeWidth="1" />
          <rect x="228" y="24" width="64" height="15" rx="3" fill="#2F5D8A" fillOpacity="0.15" />
          <text x="260" y="34" textAnchor="middle" fill="#2F5D8A" fontSize="8" fontWeight="600" className="font-code">
            09:00 Gate (24h)
          </text>

          {/* MAE Curve */}
          <path d="M 40 140 Q 150 120, 260 88 T 480 32" fill="none" stroke="#2F5D8A" strokeLinecap="round" strokeWidth="2.5" />
          <circle cx="40" cy="140" r="3.5" fill="#2F5D8A" stroke="#FFFFFF" strokeWidth="1.5" />
          <circle cx="260" cy="88" r="4" fill="#2F5D8A" stroke="#FFFFFF" strokeWidth="2" />
          <circle cx="480" cy="32" r="3.5" fill="#2F5D8A" stroke="#FFFFFF" strokeWidth="1.5" />
          <text x="265" y="82" fill="#1F2933" fontSize="9" fontWeight="600" className="font-code">594 MW</text>

          {/* X Axis */}
          <text x="40" y="170" textAnchor="middle" className="fill-[#5F6B76] font-body text-[9px]">1h</text>
          <text x="150" y="170" textAnchor="middle" className="fill-[#5F6B76] font-body text-[9px]">12h</text>
          <text x="260" y="170" textAnchor="middle" className="fill-[#2F5D8A] font-body text-[9px] font-semibold">24h</text>
          <text x="370" y="170" textAnchor="middle" className="fill-[#5F6B76] font-body text-[9px]">36h</text>
          <text x="480" y="170" textAnchor="middle" className="fill-[#5F6B76] font-body text-[9px]">48h</text>
        </svg>
      </div>

      <div className="flex items-center justify-between text-caption text-text-muted">
        <span>Gate Closure Baseline: 320 MW MAE</span>
        <span>Day-Ahead Lock: 594 MW MAE (+85.6%)</span>
      </div>
    </div>
  );
};

// 5. Error Distribution Histogram with Quantiles
export const DistributionHistogram: React.FC<{ distribution: DistributionResult }> = ({ distribution }) => {
  return (
    <div className="bg-surface border border-border rounded-xl p-5 flex flex-col gap-3">
      <div className="flex items-start justify-between">
        <div>
          <h3 className="font-h3 text-h3 text-text tracking-tight">Error Distribution &amp; Quantile Tails</h3>
          <p className="font-body-sm text-caption text-text-muted mt-0.5">
            Normalized error distribution (1,488 SPs) with empirical P10, P50, P90 quantiles
          </p>
        </div>
        <span className="px-2 py-0.5 rounded text-caption font-code font-medium bg-data-shortfall/10 border border-data-shortfall/30 text-data-shortfall-text">
          Fat Shortfall Tail
        </span>
      </div>

      <div className="relative w-full h-[220px] bg-bg/50 border border-border rounded-lg p-3">
        <svg className="w-full h-full" viewBox="0 0 500 180" preserveAspectRatio="none">
          <line x1="40" x2="480" y1="30" y2="30" stroke="#E5E5E0" strokeDasharray="2 2" strokeWidth="1" />
          <line x1="40" x2="480" y1="80" y2="80" stroke="#E5E5E0" strokeDasharray="2 2" strokeWidth="1" />
          <line x1="40" x2="480" y1="155" y2="155" stroke="#727780" strokeWidth="1" />

          {/* Shortfall Danger Zone Shading */}
          <rect x="40" y="30" width="145" height="125" fill="#C2571A" fillOpacity="0.09" />
          <text x="110" y="45" textAnchor="middle" fill="#C2571A" fontSize="8" fontWeight="600">
            SHORTFALL RISK TAIL (&lt; -200 MW)
          </text>

          {/* Bins */}
          {distribution.bins.map((b, i) => {
            const x = 50 + i * 28;
            const h = Math.min((b.count / 260) * 125, 125);
            const y = 155 - h;

            return (
              <rect
                key={b.bin_center_mw}
                x={x}
                y={y}
                width="20"
                height={h}
                fill={b.is_shortfall_tail ? '#C2571A' : '#B3CBE0'}
                fillOpacity={b.is_shortfall_tail ? 0.8 : 1}
              />
            );
          })}

          {/* Quantile Markers */}
          <line x1="112" x2="112" y1="25" y2="155" stroke="#C2571A" strokeDasharray="2 2" strokeWidth="1.5" />
          <text x="112" y="20" textAnchor="middle" fill="#C2571A" fontSize="8" fontWeight="700" className="font-code">
            P10: {distribution.p10_mw} MW
          </text>

          <line x1="240" x2="240" y1="25" y2="155" stroke="#1F2933" strokeWidth="1.5" />
          <text x="240" y="20" textAnchor="middle" fill="#1F2933" fontSize="8" fontWeight="700" className="font-code">
            Median: +{distribution.p50_median_mw} MW
          </text>

          <line x1="360" x2="360" y1="25" y2="155" stroke="#2E7D6B" strokeDasharray="2 2" strokeWidth="1.5" />
          <text x="360" y="20" textAnchor="middle" fill="#2E7D6B" fontSize="8" fontWeight="700" className="font-code">
            P90: +{distribution.p90_mw} MW
          </text>

          {/* X Axis */}
          <text x="50" y="170" textAnchor="middle" className="fill-[#5F6B76] font-body text-[9px]">-1,400</text>
          <text x="190" y="170" textAnchor="middle" className="fill-[#5F6B76] font-body text-[9px]">0 MW</text>
          <text x="360" y="170" textAnchor="middle" className="fill-[#5F6B76] font-body text-[9px]">+800</text>
          <text x="440" y="170" textAnchor="middle" className="fill-[#5F6B76] font-body text-[9px]">+1,400</text>
        </svg>
      </div>

      <div className="flex items-center justify-between text-caption text-text-muted">
        <span>Empirical shortfall probability: 27.8%</span>
        <span>Asymmetric left-tail skew</span>
      </div>
    </div>
  );
};
