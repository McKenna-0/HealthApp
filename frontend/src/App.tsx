import { NavLink, Route, Routes } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import SleepPage from './pages/SleepPage'
import WeightEnergyPage from './pages/WeightEnergyPage'
import LogPage from './pages/LogPage'
import SettingsPage from './pages/SettingsPage'

const tabs = [
  { to: '/', icon: '📊', label: 'Today' },
  { to: '/sleep', icon: '😴', label: 'Sleep' },
  { to: '/weight', icon: '⚖️', label: 'Weight' },
  { to: '/log', icon: '➕', label: 'Log' },
  { to: '/settings', icon: '⚙️', label: 'Settings' },
]

export default function App() {
  return (
    <div className="app">
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/sleep" element={<SleepPage />} />
        <Route path="/weight" element={<WeightEnergyPage />} />
        <Route path="/log" element={<LogPage />} />
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
