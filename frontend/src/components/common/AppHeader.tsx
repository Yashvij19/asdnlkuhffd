import React from 'react';
import { NavLink } from 'react-router-dom';
import { Wind, User } from 'lucide-react';

interface AppHeaderProps {
  freshnessText?: string;
}

export const AppHeader: React.FC<AppHeaderProps> = ({
  freshnessText = 'Data to 1 Feb 2026 · ingested 24 Oct',
}) => {
  const navLinkClass = ({ isActive }: { isActive: boolean }) =>
    `h-full flex items-center px-3 font-body-sm text-body-sm transition-colors ${
      isActive
        ? 'text-text border-b-2 border-accent-500 font-medium'
        : 'text-text-muted hover:text-text'
    }`;

  return (
    <header className="sticky top-0 z-50 h-14 bg-surface border-b border-border shadow-xs">
      <div className="max-w-[1280px] mx-auto px-4 sm:px-6 lg:px-8 h-14 flex items-center justify-between gap-4">
        {/* Brand / Logo */}
        <div className="flex items-center gap-4 lg:gap-8 h-full">
          <NavLink
            to="/"
            className="flex items-center gap-2.5 shrink-0 py-2 text-text hover:opacity-90 transition-opacity"
          >
            <div className="w-8 h-8 rounded-lg bg-accent-50 border border-accent-200 flex items-center justify-center text-accent-500">
              <Wind className="w-5 h-5 text-accent-500 stroke-[2.2]" />
            </div>
            <span className="font-h3 text-h3 text-text tracking-tight select-none">
              Wind Forecast Monitor
            </span>
          </NavLink>

          {/* Nav Links (Visible on tablet md and desktop lg) */}
          <nav className="hidden md:flex items-center gap-0.5 lg:gap-2 h-full">
            <NavLink to="/" end className={navLinkClass}>
              Overview
            </NavLink>
            <NavLink to="/day" className={navLinkClass}>
              Day Explorer
            </NavLink>
            <NavLink to="/accuracy" className={navLinkClass}>
              Accuracy
            </NavLink>
            <NavLink to="/deep-dive" className={navLinkClass}>
              Deep-Dive
            </NavLink>
            <NavLink to="/methodology" className={navLinkClass}>
              Methodology
            </NavLink>
          </nav>
        </div>

        {/* Right side items: Status pill + User profile */}
        <div className="flex items-center gap-3 shrink-0">
          <div className="hidden lg:flex items-center gap-2 px-2.5 py-1 rounded-full bg-surface-subtle border border-border">
            <span className="w-2 h-2 rounded-full bg-success shrink-0" />
            <span className="font-caption text-caption text-text-muted font-medium whitespace-nowrap">
              {freshnessText}
            </span>
          </div>

          <div
            className="w-8 h-8 rounded-full bg-primary flex items-center justify-center shrink-0 text-on-primary shadow-none"
            title="Trading Desk Analyst"
          >
            <User className="w-4 h-4 text-on-primary stroke-[2]" />
          </div>
        </div>
      </div>
    </header>
  );
};
