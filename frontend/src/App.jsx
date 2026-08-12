import { Navigate, Route, Routes } from 'react-router-dom'
import LoginPage from './pages/LoginPage'
import PasswordResetPage from './pages/PasswordResetPage'
import DashboardPage from './pages/DashboardPage'
import DashboardHomePage from './pages/DashboardHomePage'
import SignupPage from './pages/SignupPage'
import SettingsPage from './pages/SettingsPage'
import AnalyticsPage from './pages/AnalyticsPage'
import GuidePage from './pages/GuidePage'
import StrategyGuidePage from './pages/StrategyGuidePage'
import UpbitKeyGuidePage from './pages/UpbitKeyGuidePage'
import { getToken } from './api/client'

function RequireAuth({ children }) {
  return getToken() ? children : <Navigate to="/login" replace />
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to={getToken() ? '/dashboard' : '/login'} replace />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/password-reset" element={<PasswordResetPage />} />
      <Route path="/signup" element={<SignupPage />} />
      <Route
        path="/dashboard"
        element={
          <RequireAuth>
            <DashboardHomePage />
          </RequireAuth>
        }
      />
      <Route
        path="/dashboard/:mode"
        element={
          <RequireAuth>
            <DashboardPage />
          </RequireAuth>
        }
      />
      <Route
        path="/analytics"
        element={
          <RequireAuth>
            <AnalyticsPage />
          </RequireAuth>
        }
      />
      <Route
        path="/settings"
        element={
          <RequireAuth>
            <SettingsPage />
          </RequireAuth>
        }
      />
      <Route
        path="/guide"
        element={
          <RequireAuth>
            <GuidePage />
          </RequireAuth>
        }
      />
      <Route
        path="/guide/strategies"
        element={
          <RequireAuth>
            <StrategyGuidePage />
          </RequireAuth>
        }
      />
      <Route path="/guide/upbit-key" element={<UpbitKeyGuidePage />} />
      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  )
}
