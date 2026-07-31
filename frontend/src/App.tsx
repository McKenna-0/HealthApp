import { NavLink, Route, Routes, useLocation } from 'react-router-dom'
import { Home, ClipboardList, Dumbbell, Sparkles, Settings } from 'lucide-react'
import GlobalSyncButton from './components/GlobalSyncButton'

import Dashboard from './pages/Dashboard'
import LogPage from './pages/LogPage'
import FoodLogPage from './pages/FoodLogPage'
import FoodDetailPage from './pages/FoodDetailPage'
import WorkoutsPage from './pages/WorkoutsPage'
import ActiveWorkoutPage from './pages/ActiveWorkoutPage'
import WorkoutDetailPage from './pages/WorkoutDetailPage'
import WorkoutSummaryPage from './pages/WorkoutSummaryPage'
import ExerciseStatsPage from './pages/ExerciseStatsPage'
import RoutinesPage from './pages/RoutinesPage'
import BloodworkPage from './pages/BloodworkPage'
import InsightsPage from './pages/InsightsPage'
import AIPage from './pages/AIPage'
import SettingsPage from './pages/SettingsPage'

const TABS = [
  { to: '/', icon: Home, label: 'Home' },
  { to: '/log', icon: ClipboardList, label: 'Log' },
  { to: '/workouts', icon: Dumbbell, label: 'Workouts' },
]

export default function App() {
  const location = useLocation()
  const isActiveWorkout = location.pathname === '/workouts/active'

  const pageTitle = (() => {
    if (location.pathname === '/') return 'Today'
    if (location.pathname === '/log') return 'Log'
    if (location.pathname.startsWith('/workouts')) return 'Workouts'
    if (location.pathname === '/settings') return 'Settings'
    if (location.pathname === '/ai') return 'AI'
    if (location.pathname === '/insights') return 'Insights'
    if (location.pathname === '/bloodwork') return 'Bloodwork'
    return ''
  })()

  return (
    <div className="app">
      <header className="app-header">
        <h1>{pageTitle}</h1>
        <div className="header-actions">
          <GlobalSyncButton hide={isActiveWorkout} />
          <NavLink to="/ai" className={({isActive}) => `header-btn${isActive ? ' active' : ''}`} aria-label="AI assistant">
            <Sparkles size={20} />
          </NavLink>
          <NavLink to="/settings" className={({isActive}) => `header-btn${isActive ? ' active' : ''}`} aria-label="Settings">
            <Settings size={20} />
          </NavLink>
        </div>
      </header>

      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/log" element={<LogPage />} />
        <Route path="/log/food/:meal" element={<FoodLogPage />} />
        <Route path="/log/food/:meal/detail" element={<FoodDetailPage />} />
        <Route path="/workouts" element={<WorkoutsPage />} />
        <Route path="/workouts/active" element={<ActiveWorkoutPage />} />
        <Route path="/workouts/routines" element={<RoutinesPage />} />
        <Route path="/workouts/stats/:exerciseId" element={<ExerciseStatsPage />} />
        <Route path="/workouts/:id/summary" element={<WorkoutSummaryPage />} />
        <Route path="/workouts/:id" element={<WorkoutDetailPage />} />
        <Route path="/bloodwork" element={<BloodworkPage />} />
        <Route path="/insights" element={<InsightsPage />} />
        <Route path="/ai" element={<AIPage />} />
        <Route path="/settings" element={<SettingsPage />} />
      </Routes>

      <nav className="nav">
        {TABS.map(t => (
          <NavLink key={t.to} to={t.to} end={t.to === '/'}>
            <t.icon size={24} />
            <span>{t.label}</span>
          </NavLink>
        ))}
      </nav>
    </div>
  )
}
