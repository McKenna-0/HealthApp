import { NavLink, Route, Routes } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import SleepPage from './pages/SleepPage'
import WeightEnergyPage from './pages/WeightEnergyPage'
import LogPage from './pages/LogPage'
import SettingsPage from './pages/SettingsPage'
import WorkoutsPage from './pages/WorkoutsPage'
import WorkoutDetailPage from './pages/WorkoutDetailPage'
import BloodworkPage from './pages/BloodworkPage'
import AIPage from './pages/AIPage'
import MorePage from './pages/MorePage'

const tabs = [
  { to: '/', icon: '📊', label: 'Today' },
  { to: '/workouts', icon: '🏋️', label: 'Workouts' },
  { to: '/log', icon: '➕', label: 'Log' },
  { to: '/ai', icon: '🤖', label: 'AI' },
  { to: '/more', icon: '⋯', label: 'More' },
]

export default function App() {
  return (
    <div className="app">
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/workouts" element={<WorkoutsPage />} />
        <Route path="/workouts/:id" element={<WorkoutDetailPage />} />
        <Route path="/sleep" element={<SleepPage />} />
        <Route path="/weight" element={<WeightEnergyPage />} />
        <Route path="/log" element={<LogPage />} />
        <Route path="/bloodwork" element={<BloodworkPage />} />
        <Route path="/ai" element={<AIPage />} />
        <Route path="/more" element={<MorePage />} />
        <Route path="/settings" element={<SettingsPage />} />
      </Routes>
      <nav className="nav">
        {tabs.map((t) => (
          <NavLink key={t.to} to={t.to} className={({ isActive }) => (isActive ? 'active' : '')} end={t.to === '/'}>
            <span className="icon">{t.icon}</span>
            {t.label}
          </NavLink>
        ))}
      </nav>
    </div>
  )
}
