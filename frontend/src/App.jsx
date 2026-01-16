import React from 'react';
import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';
import LandingPage from './pages/LandingPage';
import AnalysisPage from './pages/AnalysisPage';
import AdminDashboard from './pages/AdminDashboard';
import { BarChart3 } from 'lucide-react';

function App() {
  return (
    <Router>
      <div className="min-h-screen">
        {/* Navigation */}
        <nav className="bg-white shadow-sm border-b border-gray-200">
          <div className="container mx-auto px-4">
            <div className="flex items-center justify-between h-16">
              <Link to="/" className="flex items-center gap-2 text-xl font-bold text-gray-900">
                <BarChart3 className="w-8 h-8 text-blue-600" />
                HS Code Analyzer
              </Link>
              <div className="flex gap-6">
                <Link
                  to="/"
                  className="text-gray-600 hover:text-blue-600 transition-colors font-medium"
                >
                  홈
                </Link>
                <Link
                  to="/analysis"
                  className="text-gray-600 hover:text-blue-600 transition-colors font-medium"
                >
                  분석
                </Link>
                <Link
                  to="/admin"
                  className="text-gray-600 hover:text-blue-600 transition-colors font-medium"
                >
                  대시보드
                </Link>
              </div>
            </div>
          </div>
        </nav>

        {/* Routes */}
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/analysis" element={<AnalysisPage />} />
          <Route path="/admin" element={<AdminDashboard />} />
        </Routes>
      </div>
    </Router>
  );
}

export default App;
