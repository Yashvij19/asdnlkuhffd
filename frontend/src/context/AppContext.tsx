import React, { createContext, useContext, useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';

interface AppContextType {
  decisionDate: string;
  setDecisionDate: (date: string) => void;
  cutoff: string;
  setCutoff: (cutoff: string) => void;
  confidence: number;
  setConfidence: (confidence: number) => void;
  showActuals: boolean;
  setShowActuals: (show: boolean) => void;
  periodFrom: string;
  setPeriodFrom: (from: string) => void;
  periodTo: string;
  setPeriodTo: (to: string) => void;
}

const AppContext = createContext<AppContextType | undefined>(undefined);

export const AppProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [searchParams, setSearchParams] = useSearchParams();

  // Read URL params or set defaults
  const dateParam = searchParams.get('date') || '2026-01-15';
  const cutoffParam = searchParams.get('cutoff') || '09:00';
  const confParam = parseInt(searchParams.get('conf') || '90', 10);
  const actualsParam = searchParams.get('actuals') !== 'false';
  const fromParam = searchParams.get('from') || '2026-01-01';
  const toParam = searchParams.get('to') || '2026-01-31';

  const [decisionDate, setDecisionDateState] = useState(dateParam);
  const [cutoff, setCutoffState] = useState(cutoffParam);
  const [confidence, setConfidenceState] = useState(confParam);
  const [showActuals, setShowActualsState] = useState(actualsParam);
  const [periodFrom, setPeriodFromState] = useState(fromParam);
  const [periodTo, setPeriodToState] = useState(toParam);

  // Sync state changes into URL query params
  const updateUrl = (updates: Record<string, string>) => {
    const next = new URLSearchParams(searchParams);
    Object.entries(updates).forEach(([k, v]) => {
      next.set(k, v);
    });
    setSearchParams(next, { replace: true });
  };

  const setDecisionDate = (d: string) => {
    setDecisionDateState(d);
    updateUrl({ date: d });
  };

  const setCutoff = (c: string) => {
    setCutoffState(c);
    updateUrl({ cutoff: c });
  };

  const setConfidence = (c: number) => {
    setConfidenceState(c);
    updateUrl({ conf: String(c) });
  };

  const setShowActuals = (s: boolean) => {
    setShowActualsState(s);
    updateUrl({ actuals: String(s) });
  };

  const setPeriodFrom = (f: string) => {
    setPeriodFromState(f);
    updateUrl({ from: f });
  };

  const setPeriodTo = (t: string) => {
    setPeriodToState(t);
    updateUrl({ to: t });
  };

  return (
    <AppContext.Provider
      value={{
        decisionDate,
        setDecisionDate,
        cutoff,
        setCutoff,
        confidence,
        setConfidence,
        showActuals,
        setShowActuals,
        periodFrom,
        setPeriodFrom,
        periodTo,
        setPeriodTo,
      }}
    >
      {children}
    </AppContext.Provider>
  );
};

export const useApp = () => {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error('useApp must be used within an AppProvider');
  }
  return context;
};
