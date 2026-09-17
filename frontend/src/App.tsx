import { NavLink, Route, Routes, useLocation } from 'react-router-dom'
import { Home, ClipboardList, Dumbbell, Sparkles, MoreHorizontal } from 'lucide-react'
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
import AIChatPage from './pages/AIChatPage'
import SettingsPage from './pages/SettingsPage'
import MorePage from './pages/MorePage'

const TABS = [
  { to: '/', icon: Home, label: 'Home' },
  { to: '/log', icon: ClipboardList, label: 'Log' },
  { to: '/workouts', icon: Dumbbell, label: 'Train' },
  { to: '/ai', icon: Sparkles, label: 'Coach' },
  { to: '/more', icon: MoreHorizontal, label: 'More' },
]

export default function App() {
  const location = useLocation()
  const isActiveWorkout = location.pathname === '/workouts/active'

  const pageTitle = (() => {
    if (location.pathname === '/') return 'Today'
    if (location.pathname === '/log') return 'Log'
    if (location.pathname.startsWith('/workouts')) return 'Workouts'
    if (location.pathname === '/settings') return 'Settings'
    if (location.pathname.startsWith('/ai')) return 'Coach'
    if (location.pathname === '/more') return 'More'
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
        <Route path="/ai/chat/:sessionId" element={<AIChatPage />} />
        <Route path="/more" element={<MorePage />} />
        <Route path="/settings" element={<SettingsPage />} />
      </Routes>

      <nav className="nav">
        {TABS.map(t => (
          <NavLink key={t.to} to={t.to} end={t.to === '/'}>
            <t.icon size={21} />
            <span>{t.label}</span>
          </NavLink>
        ))}
      </nav>
    </div>
  )
}
