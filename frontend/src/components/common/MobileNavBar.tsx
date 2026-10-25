import React from 'react';
import { NavLink } from 'react-router-dom';
import { Gauge, Calendar, BarChart2, Layers, BookOpen } from 'lucide-react';

export const MobileNavBar: React.FC = () => {
  const navItemClass = ({ isActive }: { isActive: boolean }) =>
    `flex flex-col items-center justify-center min-w-[56px] h-12 px-1.5 py-1 rounded-lg transition-colors ${
      isActive
        ? 'text-accent-500 bg-accent-50 font-semibold'
        : 'text-text-muted hover:text-text'
    }`;

  return (
    <nav className="md:hidden fixed bottom-0 left-0 right-0 z-50 pb-safe bg-surface/95 backdrop-blur-md border-t border-border shadow-sm">
      <div className="flex items-center justify-around h-14 px-2">
        <NavLink to="/" end className={navItemClass}>
          <Gauge className="w-5 h-5 mb-0.5 stroke-[2]" />
          <span className="font-caption text-[11px] leading-none">Overview</span>
        </NavLink>

        <NavLink to="/day" className={navItemClass}>
          <Calendar className="w-5 h-5 mb-0.5 stroke-[2]" />
          <span className="font-caption text-[11px] leading-none">Day</span>
        </NavLink>

        <NavLink to="/accuracy" className={navItemClass}>
          <BarChart2 className="w-5 h-5 mb-0.5 stroke-[2]" />
          <span className="font-caption text-[11px] leading-none">Accuracy</span>
        </NavLink>

        <NavLink to="/deep-dive" className={navItemClass}>
          <Layers className="w-5 h-5 mb-0.5 stroke-[2]" />
          <span className="font-caption text-[11px] leading-none">Deep-Dive</span>
        </NavLink>

        <NavLink to="/methodology" className={navItemClass}>
          <BookOpen className="w-5 h-5 mb-0.5 stroke-[2]" />
          <span className="font-caption text-[11px] leading-none">Method</span>
        </NavLink>
      </div>
    </nav>
  );
};
