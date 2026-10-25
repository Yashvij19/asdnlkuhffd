import React from 'react';
import { TrendingUp, AlertTriangle, CheckCircle, Info } from 'lucide-react';

export interface InsightCalloutProps {
  type: 'accent' | 'shortfall' | 'success' | 'warning';
  title: string;
  body: React.ReactNode;
  footerLabel?: string;
  footerValue?: string;
}

export const InsightCallout: React.FC<InsightCalloutProps> = ({
  type,
  title,
  body,
  footerLabel,
  footerValue,
}) => {
  const getBorderColor = () => {
    switch (type) {
      case 'shortfall':
        return 'border-data-shortfall';
      case 'success':
        return 'border-success';
      case 'warning':
        return 'border-warning-fill';
      case 'accent':
      default:
        return 'border-accent-500';
    }
  };

  const getIcon = () => {
    switch (type) {
      case 'shortfall':
        return <AlertTriangle className="w-4 h-4 text-data-shortfall" />;
      case 'success':
        return <CheckCircle className="w-4 h-4 text-success" />;
      case 'warning':
        return <AlertTriangle className="w-4 h-4 text-warning-text" />;
      case 'accent':
      default:
        return <TrendingUp className="w-4 h-4 text-accent-500" />;
    }
  };

  return (
    <div
      className={`bg-surface-subtle rounded-md p-4 border-l-2 ${getBorderColor()} flex flex-col justify-between`}
    >
      <div>
        <div className="flex items-center gap-2 mb-1.5">
          {getIcon()}
          <h4 className="font-h4 text-h4 text-text">{title}</h4>
        </div>
        <p className="font-body-sm text-body-sm text-text-muted leading-relaxed">
          {body}
        </p>
      </div>

      {(footerLabel || footerValue) && (
        <div className="mt-3 pt-2 border-t border-border/60 flex items-center justify-between font-caption text-caption">
          {footerLabel && <span className="text-text-muted">{footerLabel}</span>}
          {footerValue && (
            <span
              className={`font-code font-medium ${
                type === 'shortfall'
                  ? 'text-data-shortfall-text'
                  : type === 'success'
                  ? 'text-success'
                  : 'text-text'
              }`}
            >
              {footerValue}
            </span>
          )}
        </div>
      )}
    </div>
  );
};
