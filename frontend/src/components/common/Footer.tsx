import React from 'react';
import { NavLink } from 'react-router-dom';

export const Footer: React.FC = () => {
  return (
    <footer className="w-full bg-surface border-t border-border mt-auto mb-14 md:mb-0">
      <div className="max-w-[1280px] mx-auto px-4 sm:px-6 lg:px-8 py-6 flex flex-col sm:flex-row items-center justify-between gap-4 font-body-sm text-body-sm text-text-muted">
        <div>
          Contains BMRS data © Elexon Limited copyright and database right 2026. · v1.4.2
        </div>
        <div className="flex items-center gap-6 font-caption text-caption">
          <NavLink to="/methodology" className="text-text-muted hover:text-text transition-colors">
            Data Sources &amp; Feeds
          </NavLink>
          <span className="text-border-strong">•</span>
          <span className="text-text-muted">National Grid ESO Telemetry</span>
          <span className="text-border-strong">•</span>
          <a
            href="/api/docs"
            target="_blank"
            rel="noopener noreferrer"
            className="text-text-muted hover:text-accent-500 transition-colors"
          >
            API Docs
          </a>
        </div>
      </div>
    </footer>
  );
};
