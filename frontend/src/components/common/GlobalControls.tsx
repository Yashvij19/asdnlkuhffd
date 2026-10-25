import React, { useState } from 'react';
import { useApp } from '../../context/AppContext';
import { Calendar, Clock, ChevronLeft, ChevronRight } from 'lucide-react';

interface GlobalControlsProps {
  showActualsToggle?: boolean;
  showConfidenceSegment?: boolean;
}

export const GlobalControls: React.FC<GlobalControlsProps> = ({
  showActualsToggle = true,
  showConfidenceSegment = true,
}) => {
  const {
    decisionDate,
    setDecisionDate,
    cutoff,
    setCutoff,
    confidence,
    setConfidence,
    showActuals,
    setShowActuals,
  } = useApp();

  const [dateModalOpen, setDateModalOpen] = useState(false);
  const [cutoffModalOpen, setCutoffModalOpen] = useState(false);

  // Available days in Jan 2026
  const janDays = Array.from({ length: 31 }, (_, i) => {
    const day = String(i + 1).padStart(2, '0');
    return `2026-01-${day}`;
  });

  const handlePrevDay = () => {
    const currIdx = janDays.indexOf(decisionDate);
    if (currIdx > 0) {
      setDecisionDate(janDays[currIdx - 1]);
    }
  };

  const handleNextDay = () => {
    const currIdx = janDays.indexOf(decisionDate);
    if (currIdx < janDays.length - 1) {
      setDecisionDate(janDays[currIdx + 1]);
    }
  };

  const formatDateDisplay = (dateStr: string) => {
    try {
      const parts = dateStr.split('-');
      const day = parseInt(parts[2], 10);
      return `${day} Jan 2026`;
    } catch {
      return dateStr;
    }
  };

  return (
    <section className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 mb-6">
      <div className="flex flex-wrap items-center gap-3">
        {/* Date Stepper / Picker */}
        <div className="inline-flex items-center rounded-lg bg-surface border border-border-strong divide-x divide-border">
          <button
            type="button"
            onClick={handlePrevDay}
            disabled={decisionDate === '2026-01-01'}
            className="h-9 px-2 text-text-muted hover:text-text hover:bg-surface-subtle transition-colors disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center"
            title="Previous Day"
          >
            <ChevronLeft className="w-4 h-4 stroke-[2]" />
          </button>

          <div className="relative">
            <button
              type="button"
              onClick={() => setDateModalOpen(!dateModalOpen)}
              className="h-9 px-3 flex items-center gap-2 font-body-sm text-body-sm text-text hover:bg-surface-subtle transition-colors"
            >
              <Calendar className="w-4 h-4 text-text-muted stroke-[2]" />
              <span className="font-medium">{formatDateDisplay(decisionDate)}</span>
            </button>

            {dateModalOpen && (
              <div className="absolute top-11 left-0 z-50 w-56 p-2 bg-surface border border-border-strong rounded-lg shadow-sm animate-pop-in">
                <div className="text-caption font-label text-text-muted px-2 py-1 uppercase">
                  Select January 2026 Date
                </div>
                <div className="max-h-60 overflow-y-auto divide-y divide-border">
                  {janDays.map((d) => (
                    <button
                      key={d}
                      type="button"
                      onClick={() => {
                        setDecisionDate(d);
                        setDateModalOpen(false);
                      }}
                      className={`w-full text-left px-2 py-1.5 rounded text-body-sm transition-colors ${
                        d === decisionDate
                          ? 'bg-accent-50 text-accent-700 font-semibold'
                          : 'text-text hover:bg-surface-subtle'
                      }`}
                    >
                      {formatDateDisplay(d)}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>

          <button
            type="button"
            onClick={handleNextDay}
            disabled={decisionDate === '2026-01-31'}
            className="h-9 px-2 text-text-muted hover:text-text hover:bg-surface-subtle transition-colors disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center"
            title="Next Day"
          >
            <ChevronRight className="w-4 h-4 stroke-[2]" />
          </button>
        </div>

        {/* Cut-off Selector */}
        <div className="relative">
          <button
            type="button"
            onClick={() => setCutoffModalOpen(!cutoffModalOpen)}
            className="flex items-center gap-2 h-9 px-3 bg-surface border border-border-strong rounded-lg hover:bg-surface-subtle transition-colors"
          >
            <Clock className="w-4 h-4 text-text-muted stroke-[2]" />
            <span className="font-body-sm text-body-sm text-text font-medium">
              Cut-off: {cutoff}
            </span>
            <span className="font-caption text-caption text-text-muted pl-1 border-l border-border hidden sm:inline">
              London time
            </span>
          </button>

          {cutoffModalOpen && (
            <div className="absolute top-11 left-0 z-50 w-44 p-1.5 bg-surface border border-border-strong rounded-lg shadow-sm animate-pop-in">
              {['06:00', '08:00', '09:00', '11:00', '14:00', '18:00'].map((time) => (
                <button
                  key={time}
                  type="button"
                  onClick={() => {
                    setCutoff(time);
                    setCutoffModalOpen(false);
                  }}
                  className={`w-full text-left px-3 py-1.5 rounded text-body-sm transition-colors ${
                    time === cutoff
                      ? 'bg-accent-50 text-accent-700 font-semibold'
                      : 'text-text hover:bg-surface-subtle'
                  }`}
                >
                  {time} London
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Confidence Segmented Control */}
        {showConfidenceSegment && (
          <div className="flex items-center p-0.5 bg-surface-subtle border border-border rounded-lg h-9">
            <span className="font-caption text-caption text-text-muted px-2 font-medium hidden sm:inline">
              Confidence:
            </span>
            {[80, 90, 95, 99].map((lvl) => (
              <button
                key={lvl}
                type="button"
                onClick={() => setConfidence(lvl)}
                className={`px-2.5 py-1 font-label text-label rounded-md transition-all ${
                  confidence === lvl
                    ? 'font-semibold bg-surface text-text border border-border-strong shadow-none'
                    : 'text-text-muted hover:text-text'
                }`}
              >
                {lvl}%
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Right Controls: Show Real-time Actuals Toggle + D-1 Lock Indicator */}
      <div className="flex items-center gap-3">
        {showActualsToggle && (
          <label className="flex items-center gap-2 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={showActuals}
              onChange={(e) => setShowActuals(e.target.checked)}
              className="h-4 w-4 rounded-sm border-border-strong text-accent-500 focus:ring-accent-500 cursor-pointer"
            />
            <span className="font-body-sm text-body-sm text-text">
              Show real-time actuals
            </span>
          </label>
        )}

        <div className="h-4 w-px bg-border hidden sm:block" />

        <span className="font-caption text-caption text-text-muted flex items-center gap-1.5">
          <span className="inline-block w-2 h-2 rounded-full bg-success" />
          Lock: Day-Ahead D-1
        </span>
      </div>
    </section>
  );
};
