import { NavLink, Route, Routes } from 'react-router-dom'
import GlobalSyncButton from './components/GlobalSyncButton'
import Dashboard from './pages/Dashboard'
import SleepPage from './pages/SleepPage'
import WeightEnergyPage from './pages/WeightEnergyPage'
import LogPage from './pages/LogPage'
import FoodLogPage from './pages/FoodLogPage'
import CheckinPage from './pages/CheckinPage'
import OtherLogsPage from './pages/OtherLogsPage'
import SettingsPage from './pages/SettingsPage'
import WorkoutsPage from './pages/WorkoutsPage'
import WorkoutDetailPage from './pages/WorkoutDetailPage'
import FoodDetailPage from './pages/FoodDetailPage'
import ActiveWorkoutPage from './pages/ActiveWorkoutPage'
import WorkoutSummaryPage from './pages/WorkoutSummaryPage'
import RoutinesPage from './pages/RoutinesPage'
import ExerciseStatsPage from './pages/ExerciseStatsPage'
import BloodworkPage from './pages/BloodworkPage'
import AIPage from './pages/AIPage'
import MorePage from './pages/MorePage'
import InsightsPage from './pages/InsightsPage'

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
      <GlobalSyncButton />
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/workouts" element={<WorkoutsPage />} />
        <Route path="/workouts/active" element={<ActiveWorkoutPage />} />
        <Route path="/workouts/routines" element={<RoutinesPage />} />
        <Route path="/workouts/stats/:exerciseId" element={<ExerciseStatsPage />} />
        <Route path="/workouts/:id/summary" element={<WorkoutSummaryPage />} />
        <Route path="/workouts/:id" element={<WorkoutDetailPage />} />
        <Route path="/sleep" element={<SleepPage />} />
        <Route path="/weight" element={<WeightEnergyPage />} />
        <Route path="/log" element={<LogPage />} />
        <Route path="/log/food/:meal/detail" element={<FoodDetailPage />} />
        <Route path="/log/food/:meal" element={<FoodLogPage />} />
        <Route path="/log/checkin" element={<CheckinPage />} />
        <Route path="/log/other" element={<OtherLogsPage />} />
        <Route path="/bloodwork" element={<BloodworkPage />} />
        <Route path="/insights" element={<InsightsPage />} />
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
