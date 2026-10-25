import React from 'react';
import { HelpCircle, TrendingDown, TrendingUp, AlertTriangle, CheckCircle } from 'lucide-react';

export interface KpiTileProps {
  label: string;
  value: string | number;
  unit?: string;
  subLabel?: string;
  subValue?: string;
  tooltip?: string;
  badgeText?: string;
  badgeType?: 'success' | 'warning' | 'error' | 'shortfall' | 'accent' | 'neutral';
  deltaText?: string;
  deltaType?: 'positive' | 'negative' | 'neutral' | 'shortfall';
  valueColorClass?: string;
}

export const KpiTile: React.FC<KpiTileProps> = ({
  label,
  value,
  unit,
  subLabel,
  subValue,
  tooltip,
  badgeText,
  badgeType = 'neutral',
  deltaText,
  deltaType = 'neutral',
  valueColorClass = 'text-text',
}) => {
  const getBadgeClass = () => {
    switch (badgeType) {
      case 'success':
        return 'bg-success/10 text-success border-success/30';
      case 'warning':
        return 'bg-warning-fill/10 text-warning-text border-warning-fill/30';
      case 'error':
      case 'shortfall':
        return 'bg-data-shortfall/10 text-data-shortfall-text border-data-shortfall/30';
      case 'accent':
        return 'bg-accent-50 text-accent-700 border-accent-200';
      default:
        return 'bg-surface-subtle text-text-muted border-border';
    }
  };

  return (
    <div className="bg-surface border border-border rounded-xl p-5 flex flex-col justify-between">
      {/* Header Row */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-1.5 min-w-0">
          <span className="font-label text-label text-text-muted truncate">
            {label}
          </span>
          {tooltip && (
            <span
              className="text-text-muted hover:text-text cursor-help transition-colors"
              title={tooltip}
            >
              <HelpCircle className="w-3.5 h-3.5 stroke-[2]" />
            </span>
          )}
        </div>

        {badgeText && (
          <span
            className={`px-2 py-0.5 rounded-full text-caption font-medium border text-xs whitespace-nowrap ${getBadgeClass()}`}
          >
            {badgeText}
          </span>
        )}
      </div>

      {/* Main KPI Value */}
      <div className="my-2.5">
        <div className="flex items-baseline gap-2">
          <span
            className={`font-kpi-value text-kpi-value ${valueColorClass} font-semibold tabular-nums`}
          >
            {value}
          </span>
          {unit && (
            <span className="font-kpi-unit text-kpi-unit text-text-muted font-medium">
              {unit}
            </span>
          )}
        </div>
      </div>

      {/* Footer / Context Row */}
      {(subLabel || subValue || deltaText) && (
        <div className="pt-2.5 border-t border-border flex items-center justify-between text-body-sm font-body-sm gap-2">
          {subLabel && (
            <span className="font-caption text-caption text-text-muted truncate min-w-0">
              {subLabel}
            </span>
          )}

          {subValue && (
            <span className="font-code text-caption tabular-nums text-text font-medium shrink-0">
              {subValue}
            </span>
          )}

          {deltaText && (
            <span
              className={`font-caption text-caption flex items-center gap-1 font-medium ${
                deltaType === 'shortfall' || deltaType === 'negative'
                  ? 'text-data-shortfall-text'
                  : deltaType === 'positive'
                  ? 'text-success'
                  : 'text-text-muted'
              }`}
            >
              {deltaType === 'positive' && <TrendingUp className="w-3.5 h-3.5" />}
              {deltaType === 'negative' && <TrendingDown className="w-3.5 h-3.5" />}
              {deltaType === 'shortfall' && <AlertTriangle className="w-3.5 h-3.5 text-data-shortfall" />}
              {deltaText}
            </span>
          )}
        </div>
      )}
    </div>
  );
};
