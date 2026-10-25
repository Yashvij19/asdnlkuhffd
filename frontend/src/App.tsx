import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AppProvider } from './context/AppContext';
import { AppHeader } from './components/common/AppHeader';
import { MobileNavBar } from './components/common/MobileNavBar';
import { Footer } from './components/common/Footer';
import { OverviewPage } from './pages/OverviewPage';
import { DayExplorerPage } from './pages/DayExplorerPage';
import { AccuracyDashboardPage } from './pages/AccuracyDashboardPage';
import { ErrorDeepDivePage } from './pages/ErrorDeepDivePage';
import { MethodologyPage } from './pages/MethodologyPage';

export const App: React.FC = () => {
  return (
    <BrowserRouter>
      <AppProvider>
        <div className="min-h-screen flex flex-col bg-bg text-text selection:bg-accent-100 font-sans antialiased">
          {/* Skip link for screen reader and keyboard accessibility */}
          <a
            href="#main-content"
            className="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-50 focus:px-3 focus:py-2 focus:bg-accent focus:text-white focus:rounded focus:shadow-md focus:text-xs focus:font-medium"
          >
            Skip to main content
          </a>

          {/* Sticky top desktop & mobile header */}
          <AppHeader />

          {/* Main page content area */}
          <main id="main-content" className="flex-1 pb-20 md:pb-10">
            <Routes>
              <Route path="/" element={<OverviewPage />} />
              <Route path="/day" element={<DayExplorerPage />} />
              <Route path="/accuracy" element={<AccuracyDashboardPage />} />
              <Route path="/deep-dive" element={<ErrorDeepDivePage />} />
              <Route path="/methodology" element={<MethodologyPage />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </main>

          {/* Persistent footer */}
          <Footer />

          {/* Fixed bottom navigation for mobile screen sizes (< 768px) */}
          <MobileNavBar />
        </div>
      </AppProvider>
    </BrowserRouter>
  );
};

export default App;
