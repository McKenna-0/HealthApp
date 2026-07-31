# UI Revamp Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the entire frontend with a clean minimal aesthetic, 3-tab navigation, customizable dashboard with metric drill-downs, workout UX fixes, swipe-to-delete, and PWA notifications.

**Architecture:** Frontend-only redesign. No backend changes. Replaces the 5-tab emoji nav with a 3-tab Lucide icon nav (Home/Log/Workouts). Dashboard becomes a single scrollable page with customizable metrics that drill down into detail views. SleepPage and WeightEnergyPage are absorbed into drill-downs. MorePage is eliminated. Check-in becomes a bottom sheet. Swipe-to-delete replaces all X buttons.

**Tech Stack:** React 19, TypeScript, Vite, React Router 7, TanStack React Query 5, Recharts 3, Lucide React (new), date-fns 4

## Global Constraints

- iPhone 14 PWA target — all layouts must work in iOS Safari standalone mode
- Safe area insets: `env(safe-area-inset-top)` and `env(safe-area-inset-bottom)` on all fixed elements
- Minimum 44px tap targets on all interactive elements
- Dark theme only — color palette defined in CSS custom properties
- No shadows on cards — clean minimal aesthetic
- Typography scale: Display 1.75rem/700, Title 1.15rem/600, Body 0.9rem/400, Caption 0.75rem/400
- Spacing tokens: 4, 8, 12, 16, 24, 32 (px, base unit 4px)
- Lucide React icons at 20px in UI, 24px in nav — no emojis except mood selector
- All "Loading..." text replaced with skeleton pulse animations
- Swipe-to-delete everywhere instead of X buttons
- localStorage key `dashboard-metrics-config` for metric customization
- Existing API contract unchanged — no new backend endpoints for UI changes
- Spec: `docs/superpowers/specs/2026-07-31-ui-revamp-design.md`

---

### Task 1: Design System Foundation & Dependencies

**Files:**
- Modify: `frontend/package.json` — add lucide-react dependency
- Modify: `frontend/src/index.css:1-983` — replace all CSS custom properties, typography, card styles, spacing
- Create: `frontend/src/components/SkeletonLoader.tsx` — pulse-animated placeholder component

**Interfaces:**
- Produces: CSS custom properties (`--bg`, `--card`, `--card-elevated`, `--border`, `--text`, `--muted`, `--accent`, `--green`, `--red`, `--amber`), typography classes (`.text-display`, `.text-title`, `.text-body`, `.text-caption`), `SkeletonLoader` component (`props: { width?: string, height?: string, borderRadius?: string }`)

- [ ] **Step 1: Install lucide-react**

```bash
cd frontend && npm install lucide-react
```

- [ ] **Step 2: Update CSS custom properties and add typography scale**

Replace the `:root` block and add typography classes in `frontend/src/index.css`. Replace lines 1-11 (the `:root` block) with:

```css
:root {
  --bg: #0B1120;
  --card: #151E2F;
  --card-elevated: #1C2740;
  --border: #243044;
  --text: #E8ECF1;
  --muted: #7A8BA5;
  --accent: #3B9EFF;
  --green: #34D399;
  --red: #F87171;
  --amber: #FBBF24;
}
```

Add typography utility classes after the `:root` block:

```css
.text-display { font-size: 1.75rem; font-weight: 700; color: var(--text); }
.text-title { font-size: 1.15rem; font-weight: 600; color: var(--text); }
.text-body { font-size: 0.9rem; font-weight: 400; color: var(--text); }
.text-caption { font-size: 0.75rem; font-weight: 400; color: var(--muted); }
```

- [ ] **Step 3: Update card, body, and base element styles**

In `index.css`, update the `body` background to use `--bg`. Update `.card` to:

```css
.card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 16px;
  margin-bottom: 12px;
}
```

Update `h1` to `font-size: 1.75rem; font-weight: 700;` and `h2` to `font-size: 1.15rem; font-weight: 600;`.

Update `.metric-card` padding to `12px`, border-radius to `14px`.

Update `.nav` bottom bar to have `background: var(--card); border-top: 1px solid var(--border);`.

- [ ] **Step 4: Add skeleton loader animation and utility classes**

Add to `index.css`:

```css
/* Skeleton loader */
@keyframes skeleton-pulse {
  0%, 100% { opacity: 0.4; }
  50% { opacity: 0.15; }
}

.skeleton {
  background: var(--border);
  border-radius: 8px;
  animation: skeleton-pulse 1.5s ease-in-out infinite;
}

/* Elevated card (for sheets, modals) */
.card-elevated {
  background: var(--card-elevated);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 16px;
}

/* Slide-up transition */
.slide-up-enter { transform: translateY(100%); }
.slide-up-enter-active { transform: translateY(0); transition: transform 300ms ease-out; }
.slide-up-exit-active { transform: translateY(100%); transition: transform 200ms ease-in; }
```

- [ ] **Step 5: Create SkeletonLoader component**

Create `frontend/src/components/SkeletonLoader.tsx`:

```tsx
export default function SkeletonLoader({
  width = '100%',
  height = '16px',
  borderRadius = '8px',
}: {
  width?: string
  height?: string
  borderRadius?: string
}) {
  return (
    <div
      className="skeleton"
      style={{ width, height, borderRadius }}
    />
  )
}
```

- [ ] **Step 6: Verify build passes**

```bash
cd frontend && npm run build
```

Expected: Build succeeds with no errors. Lucide-react is installed. CSS compiles.

- [ ] **Step 7: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/index.css frontend/src/components/SkeletonLoader.tsx
git commit -m "feat: design system foundation — new color palette, typography scale, skeleton loader"
```

---

### Task 2: Shared Components — SwipeToDelete & BottomSheet

**Files:**
- Create: `frontend/src/components/SwipeToDelete.tsx` — swipe-left-to-reveal-delete wrapper
- Create: `frontend/src/components/BottomSheet.tsx` — modal bottom sheet with backdrop
- Modify: `frontend/src/index.css` — add swipe and sheet styles

**Interfaces:**
- Produces: `SwipeToDelete` component (`props: { onDelete: () => void, confirm?: boolean, children: ReactNode }`), `BottomSheet` component (`props: { open: boolean, onClose: () => void, title?: string, children: ReactNode }`)

- [ ] **Step 1: Add swipe-to-delete styles to index.css**

```css
/* Swipe to delete */
.swipe-container {
  position: relative;
  overflow: hidden;
  border-radius: 14px;
}

.swipe-content {
  position: relative;
  z-index: 1;
  background: var(--card);
  transition: transform 0.2s ease;
  touch-action: pan-y;
}

.swipe-delete-bg {
  position: absolute;
  top: 0;
  right: 0;
  bottom: 0;
  width: 100%;
  background: var(--red);
  display: flex;
  align-items: center;
  justify-content: flex-end;
  padding-right: 24px;
  color: white;
}

.swipe-deleting {
  transition: max-height 0.2s ease, opacity 0.2s ease;
  max-height: 0 !important;
  opacity: 0;
  margin-bottom: 0 !important;
  overflow: hidden;
}
```

- [ ] **Step 2: Create SwipeToDelete component**

Create `frontend/src/components/SwipeToDelete.tsx`:

```tsx
import { useRef, useState, type ReactNode } from 'react'
import { Trash2 } from 'lucide-react'

export default function SwipeToDelete({
  onDelete,
  confirm = false,
  children,
}: {
  onDelete: () => void
  confirm?: boolean
  children: ReactNode
}) {
  const startX = useRef(0)
  const currentX = useRef(0)
  const [offset, setOffset] = useState(0)
  const [deleting, setDeleting] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  const threshold = containerRef.current
    ? containerRef.current.offsetWidth * 0.5
    : 150

  function handleTouchStart(e: React.TouchEvent) {
    startX.current = e.touches[0].clientX
    currentX.current = startX.current
  }

  function handleTouchMove(e: React.TouchEvent) {
    currentX.current = e.touches[0].clientX
    const diff = startX.current - currentX.current
    if (diff > 0) setOffset(diff)
  }

  function handleTouchEnd() {
    if (offset > threshold) {
      triggerDelete()
    } else {
      setOffset(0)
    }
  }

  function triggerDelete() {
    if (confirm && !window.confirm('Are you sure?')) {
      setOffset(0)
      return
    }
    if (navigator.vibrate) navigator.vibrate(10)
    setDeleting(true)
    setTimeout(() => onDelete(), 200)
  }

  if (deleting) {
    return <div className="swipe-deleting" style={{ maxHeight: 0 }} />
  }

  return (
    <div className="swipe-container" ref={containerRef}>
      <div className="swipe-delete-bg" onClick={() => triggerDelete()}>
        <Trash2 size={20} />
      </div>
      <div
        className="swipe-content"
        style={{ transform: `translateX(-${offset}px)` }}
        onTouchStart={handleTouchStart}
        onTouchMove={handleTouchMove}
        onTouchEnd={handleTouchEnd}
      >
        {children}
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Update bottom sheet styles in index.css**

Replace the existing `.sheet-backdrop` / `.sheet` styles with:

```css
/* Bottom sheet */
.sheet-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  z-index: 100;
  animation: fade-in 0.2s ease;
}

@keyframes fade-in {
  from { opacity: 0; }
  to { opacity: 1; }
}

.sheet {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  max-height: 92vh;
  background: var(--card-elevated);
  border-top-left-radius: 20px;
  border-top-right-radius: 20px;
  z-index: 101;
  padding: 0 16px calc(16px + env(safe-area-inset-bottom));
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
  animation: sheet-up 0.3s ease-out;
}

@keyframes sheet-up {
  from { transform: translateY(100%); }
  to { transform: translateY(0); }
}

.sheet-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 0 12px;
  position: sticky;
  top: 0;
  background: var(--card-elevated);
  z-index: 1;
}

.sheet-handle {
  width: 36px;
  height: 4px;
  background: var(--border);
  border-radius: 2px;
  margin: 8px auto 0;
}
```

- [ ] **Step 4: Create BottomSheet component**

Create `frontend/src/components/BottomSheet.tsx`:

```tsx
import { useEffect, type ReactNode } from 'react'
import { X } from 'lucide-react'

export default function BottomSheet({
  open,
  onClose,
  title,
  children,
}: {
  open: boolean
  onClose: () => void
  title?: string
  children: ReactNode
}) {
  useEffect(() => {
    if (open) document.body.style.overflow = 'hidden'
    return () => { document.body.style.overflow = '' }
  }, [open])

  if (!open) return null

  return (
    <>
      <div className="sheet-backdrop" onClick={onClose} />
      <div className="sheet">
        <div className="sheet-handle" />
        {title && (
          <div className="sheet-header">
            <span className="text-title">{title}</span>
            <button
              onClick={onClose}
              style={{ background: 'none', border: 'none', color: 'var(--muted)', padding: 8 }}
              aria-label="Close"
            >
              <X size={20} />
            </button>
          </div>
        )}
        {children}
      </div>
    </>
  )
}
```

- [ ] **Step 5: Verify build passes**

```bash
cd frontend && npm run build
```

Expected: Build succeeds.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/SwipeToDelete.tsx frontend/src/components/BottomSheet.tsx frontend/src/index.css
git commit -m "feat: add SwipeToDelete and BottomSheet shared components"
```

---

### Task 3: App Shell — 3-Tab Navigation & Header

**Files:**
- Modify: `frontend/src/App.tsx:1-66` — replace 5-tab emoji nav with 3-tab Lucide nav, add header bar with gear/AI/sync icons, update routes
- Modify: `frontend/src/index.css` — update `.nav` styles, add `.app-header` styles
- Delete (mark unused): `frontend/src/pages/MorePage.tsx` — eliminated
- Modify: `frontend/src/components/GlobalSyncButton.tsx` — restyle as header icon, hide during active workout

**Interfaces:**
- Consumes: Lucide icons from `lucide-react`
- Produces: New `App` component with 3-tab nav + header bar. Routes reorganized. `GlobalSyncButton` accepts `hide` prop.

- [ ] **Step 1: Add header bar styles to index.css**

```css
/* App header */
.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  padding-top: calc(12px + env(safe-area-inset-top));
  border-bottom: 1px solid var(--border);
  position: sticky;
  top: 0;
  background: var(--bg);
  z-index: 50;
}

.app-header h1 {
  margin: 0;
  font-size: 1.15rem;
  font-weight: 600;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-btn {
  background: none;
  border: none;
  color: var(--muted);
  padding: 8px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 44px;
  min-height: 44px;
}

.header-btn:active {
  opacity: 0.7;
}
```

- [ ] **Step 2: Update nav styles in index.css**

Replace the existing `.nav`, `.nav a`, `.nav a.active`, `.nav .icon` rules with:

```css
.nav {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  display: flex;
  justify-content: space-around;
  background: var(--card);
  border-top: 1px solid var(--border);
  padding: 8px 0;
  padding-bottom: calc(8px + env(safe-area-inset-bottom));
  z-index: 90;
}

.nav a {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  text-decoration: none;
  color: var(--muted);
  font-size: 0.65rem;
  font-weight: 500;
  padding: 4px 16px;
  min-width: 64px;
  min-height: 44px;
  justify-content: center;
}

.nav a.active {
  color: var(--accent);
}
```

- [ ] **Step 3: Update GlobalSyncButton to header style**

Rewrite `frontend/src/components/GlobalSyncButton.tsx` to accept a `hide` prop and render as a header button instead of a floating circle:

```tsx
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { RefreshCw } from 'lucide-react'
import { apiGet, apiPost } from '../api/client'
import type { SyncStatus } from '../api/types'

export default function GlobalSyncButton({ hide = false }: { hide?: boolean }) {
  const qc = useQueryClient()
  const { data: st } = useQuery<SyncStatus>({
    queryKey: ['sync-status'],
    queryFn: () => apiGet('/api/sync/status'),
    refetchInterval: 300_000,
  })
  const sync = useMutation({
    mutationFn: () => apiPost('/api/sync'),
    onSuccess: () => {
      qc.invalidateQueries()
    },
  })

  if (hide) return null

  const stale = st && st.last_success &&
    (Date.now() - new Date(st.last_success).getTime()) > 6 * 3600_000
  const error = st?.error

  const color = sync.isPending ? 'var(--accent)' :
    error ? 'var(--red)' :
    stale ? 'var(--amber)' : 'var(--muted)'

  return (
    <button
      className="header-btn"
      onClick={() => sync.mutate()}
      disabled={sync.isPending}
      aria-label="Sync data"
    >
      <RefreshCw
        size={20}
        color={color}
        style={sync.isPending ? { animation: 'spin 1s linear infinite' } : undefined}
      />
    </button>
  )
}
```

Add spin animation to `index.css` if not already present:

```css
@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
```

- [ ] **Step 4: Rewrite App.tsx with 3-tab nav and header**

Rewrite `frontend/src/App.tsx`:

```tsx
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
          <NavLink to="/ai" className="header-btn" aria-label="AI assistant">
            <Sparkles size={20} />
          </NavLink>
          <NavLink to="/settings" className="header-btn" aria-label="Settings">
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
```

- [ ] **Step 5: Delete MorePage**

Delete `frontend/src/pages/MorePage.tsx`. Remove any remaining imports of it.

- [ ] **Step 6: Update `.app` container padding in index.css**

Update the main `.app` content area padding to account for new header (sticky, so no top padding needed) and bottom nav:

```css
.app {
  max-width: 720px;
  margin: 0 auto;
  padding-bottom: calc(76px + env(safe-area-inset-bottom));
  min-height: 100dvh;
}
```

- [ ] **Step 7: Verify build passes and test navigation**

```bash
cd frontend && npm run build
```

Expected: Build succeeds. MorePage removed. 3 tabs render. Header shows sync/AI/settings icons.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat: 3-tab navigation with header bar, remove MorePage"
```

---

### Task 4: Home Dashboard Redesign

**Files:**
- Rewrite: `frontend/src/pages/Dashboard.tsx` — customizable metrics row, recent activities, log summary, trends, insights, readiness
- Create: `frontend/src/components/MetricDrillDown.tsx` — slide-up detail view framework
- Modify: `frontend/src/components/MetricCard.tsx` — restyle with Lucide icons, delta display, tap handler
- Modify: `frontend/src/components/SyncStatusCard.tsx` — restyle for new design system

**Interfaces:**
- Consumes: `Dashboard`, `CorrelationsResponse`, `Workout` types from `api/types.ts`. `SkeletonLoader`, `apiGet` from existing modules.
- Produces: `Dashboard` page with customizable metrics. `MetricDrillDown` component (`props: { metric: string, open: boolean, onClose: () => void }`). Updated `MetricCard` component.

- [ ] **Step 1: Create metrics configuration types and defaults**

Add to `frontend/src/api/types.ts`:

```ts
export interface MetricConfig {
  id: string
  label: string
  icon: string  // lucide icon name
  unit?: string
  enabled: boolean
  order: number
}
```

- [ ] **Step 2: Restyle MetricCard component**

Rewrite `frontend/src/components/MetricCard.tsx`:

```tsx
import type { ReactNode } from 'react'

export default function MetricCard({
  icon,
  label,
  value,
  sub,
  delta,
  onClick,
}: {
  icon?: ReactNode
  label: string
  value: string | number | null
  sub?: string
  delta?: { value: number; suffix?: string }
  onClick?: () => void
}) {
  const deltaColor = delta
    ? delta.value > 0 ? 'var(--green)'
    : delta.value < 0 ? 'var(--red)'
    : 'var(--muted)'
    : undefined

  return (
    <div
      className="metric-card"
      onClick={onClick}
      style={onClick ? { cursor: 'pointer' } : undefined}
    >
      {icon && <div style={{ color: 'var(--muted)', marginBottom: 4 }}>{icon}</div>}
      <div className="text-caption" style={{ textTransform: 'uppercase', letterSpacing: '0.5px' }}>
        {label}
      </div>
      <div className="text-display" style={{ fontSize: '1.25rem', margin: '4px 0 2px' }}>
        {value ?? '–'}
      </div>
      {delta && (
        <div style={{ fontSize: '0.72rem', color: deltaColor }}>
          {delta.value > 0 ? '+' : ''}{delta.value}{delta.suffix || ''}
        </div>
      )}
      {sub && <div className="text-caption">{sub}</div>}
    </div>
  )
}
```

- [ ] **Step 3: Create the metric drill-down container**

Create `frontend/src/components/MetricDrillDown.tsx`:

```tsx
import { type ReactNode } from 'react'
import { ArrowLeft } from 'lucide-react'

export default function MetricDrillDown({
  open,
  onClose,
  title,
  value,
  children,
}: {
  open: boolean
  onClose: () => void
  title: string
  value?: string | number | null
  children: ReactNode
}) {
  if (!open) return null

  return (
    <div style={{
      position: 'fixed',
      inset: 0,
      background: 'var(--bg)',
      zIndex: 200,
      overflowY: 'auto',
      WebkitOverflowScrolling: 'touch',
      animation: 'sheet-up 0.3s ease-out',
    }}>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        padding: '16px',
        paddingTop: 'calc(16px + env(safe-area-inset-top))',
        borderBottom: '1px solid var(--border)',
        position: 'sticky',
        top: 0,
        background: 'var(--bg)',
        zIndex: 1,
      }}>
        <button
          onClick={onClose}
          style={{ background: 'none', border: 'none', color: 'var(--text)', padding: 8, minWidth: 44, minHeight: 44, display: 'flex', alignItems: 'center' }}
          aria-label="Back"
        >
          <ArrowLeft size={20} />
        </button>
        <div>
          <div className="text-title">{title}</div>
          {value != null && <div className="text-display">{value}</div>}
        </div>
      </div>
      <div style={{ padding: 16, paddingBottom: 'calc(32px + env(safe-area-inset-bottom))' }}>
        {children}
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Rewrite Dashboard page**

Rewrite `frontend/src/pages/Dashboard.tsx` with the new layout. This is a large file — key sections:

```tsx
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
  Heart, Moon, Footprints, Flame, Activity, Battery,
  TrendingUp, TrendingDown, Minus, ChevronRight, Pencil
} from 'lucide-react'
import { ResponsiveContainer, LineChart, Line, YAxis } from 'recharts'
import { apiGet } from '../api/client'
import type { Dashboard as DashboardData, CorrelationsResponse, Workout } from '../api/types'
import MetricCard from '../components/MetricCard'
import MetricDrillDown from '../components/MetricDrillDown'
import SyncStatusCard from '../components/SyncStatusCard'
import SkeletonLoader from '../components/SkeletonLoader'

const DEFAULT_METRICS = ['hrv', 'sleep_score', 'calories_out', 'steps', 'resting_hr', 'body_battery']

const METRIC_DEFS: Record<string, { label: string, icon: typeof Heart, unit?: string }> = {
  hrv: { label: 'HRV', icon: Activity, unit: 'ms' },
  sleep_score: { label: 'Sleep', icon: Moon },
  calories_out: { label: 'Cal Burned', icon: Flame, unit: 'kcal' },
  steps: { label: 'Steps', icon: Footprints },
  resting_hr: { label: 'Rest HR', icon: Heart, unit: 'bpm' },
  body_battery: { label: 'Battery', icon: Battery },
}

function getMetricValue(day: DashboardData['days'][0] | undefined, key: string): number | null {
  if (!day) return null
  const map: Record<string, number | null> = {
    hrv: day.hrv, sleep_score: day.sleep_score, calories_out: day.calories_out,
    steps: day.steps, resting_hr: day.resting_hr, body_battery: day.body_battery,
  }
  return map[key] ?? null
}

export default function Dashboard() {
  const [drillDown, setDrillDown] = useState<string | null>(null)
  const [metricsConfig] = useState<string[]>(() => {
    const saved = localStorage.getItem('dashboard-metrics-config')
    return saved ? JSON.parse(saved) : DEFAULT_METRICS
  })

  const { data: dash, isLoading } = useQuery<DashboardData>({
    queryKey: ['dashboard', 30],
    queryFn: () => apiGet('/api/analytics/dashboard?days=30'),
  })

  const { data: workouts } = useQuery<Workout[]>({
    queryKey: ['workouts'],
    queryFn: () => apiGet('/api/workouts/'),
  })

  const { data: correlations } = useQuery<CorrelationsResponse>({
    queryKey: ['correlations'],
    queryFn: () => apiGet('/api/analytics/correlations?days=90'),
  })

  const today = dash?.days?.[dash.days.length - 1]
  const avg7 = dash?.averages_7d
  const recentWorkouts = workouts?.slice(0, 3)

  return (
    <div style={{ padding: '16px' }}>
      <SyncStatusCard />

      {/* Metrics Row */}
      <div style={{
        display: 'flex',
        gap: 8,
        overflowX: 'auto',
        paddingBottom: 8,
        WebkitOverflowScrolling: 'touch',
        scrollSnapType: 'x mandatory',
      }}>
        {isLoading ? (
          Array.from({ length: 4 }).map((_, i) => (
            <div key={i} style={{ minWidth: 120, flex: '0 0 auto' }}>
              <SkeletonLoader height="90px" borderRadius="14px" />
            </div>
          ))
        ) : (
          metricsConfig.map(key => {
            const def = METRIC_DEFS[key]
            if (!def) return null
            const val = getMetricValue(today, key)
            const avgVal = avg7 ? getMetricValue({ ...today!, ...avg7 } as any, key) : null
            const delta = val != null && avgVal != null ? +(val - avgVal).toFixed(1) : undefined
            const Icon = def.icon
            return (
              <div key={key} style={{ minWidth: 120, flex: '0 0 auto', scrollSnapAlign: 'start' }}>
                <MetricCard
                  icon={<Icon size={18} />}
                  label={def.label}
                  value={val != null ? `${val}${def.unit ? '' : ''}` : null}
                  delta={delta != null ? { value: delta, suffix: def.unit ? ` ${def.unit}` : '' } : undefined}
                  onClick={() => setDrillDown(key)}
                />
              </div>
            )
          })
        )}
      </div>

      {/* Recent Activities */}
      {recentWorkouts && recentWorkouts.length > 0 && (
        <div className="card" style={{ marginTop: 12 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <span className="text-title">Recent Activities</span>
            <Link to="/workouts" style={{ color: 'var(--accent)', fontSize: '0.8rem', textDecoration: 'none', display: 'flex', alignItems: 'center', gap: 4 }}>
              See all <ChevronRight size={14} />
            </Link>
          </div>
          {recentWorkouts.map(w => (
            <Link
              key={w.id}
              to={`/workouts/${w.id}`}
              style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '10px 0', borderBottom: '1px solid var(--border)', textDecoration: 'none', color: 'var(--text)' }}
            >
              <Activity size={18} color="var(--muted)" />
              <div style={{ flex: 1 }}>
                <div className="text-body">{w.name || w.activity_type}</div>
                <div className="text-caption">{w.date} · {w.duration_min}min</div>
              </div>
              <ChevronRight size={16} color="var(--muted)" />
            </Link>
          ))}
        </div>
      )}

      {/* Today's Log Summary */}
      <Link to="/log" style={{ textDecoration: 'none', color: 'inherit' }}>
        <div className="card" style={{ marginTop: 12 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
            <span className="text-title">Today's Log</span>
            <ChevronRight size={16} color="var(--muted)" />
          </div>
          {today ? (
            <div style={{ display: 'flex', gap: 16 }}>
              <div>
                <div className="text-caption">Calories</div>
                <div className="text-body" style={{ fontWeight: 600 }}>{today.calories_in ?? '–'}</div>
              </div>
              <div>
                <div className="text-caption">Burned</div>
                <div className="text-body" style={{ fontWeight: 600 }}>{today.calories_out ?? '–'}</div>
              </div>
              <div>
                <div className="text-caption">Balance</div>
                <div className="text-body" style={{
                  fontWeight: 600,
                  color: today.balance != null ? (today.balance > 0 ? 'var(--red)' : 'var(--green)') : undefined,
                }}>
                  {today.balance != null ? `${today.balance > 0 ? '+' : ''}${today.balance}` : '–'}
                </div>
              </div>
            </div>
          ) : (
            <div className="text-caption">No data yet. Check in to start tracking.</div>
          )}
        </div>
      </Link>

      {/* Trends sparklines */}
      {dash && dash.days.length > 7 && (
        <div className="card" style={{ marginTop: 12 }}>
          <div className="text-title" style={{ marginBottom: 12 }}>Trends</div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            {metricsConfig.slice(0, 4).map(key => {
              const def = METRIC_DEFS[key]
              if (!def) return null
              const chartData = dash.days.map(d => ({ v: getMetricValue(d, key) })).filter(d => d.v != null)
              if (chartData.length < 3) return null
              return (
                <div key={key} onClick={() => setDrillDown(key)} style={{ cursor: 'pointer' }}>
                  <div className="text-caption" style={{ marginBottom: 4 }}>{def.label}</div>
                  <ResponsiveContainer width="100%" height={50}>
                    <LineChart data={chartData}>
                      <YAxis domain={['dataMin', 'dataMax']} hide />
                      <Line type="monotone" dataKey="v" stroke="var(--accent)" strokeWidth={1.5} dot={false} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* AI Insights */}
      {correlations?.insights && correlations.insights.filter(i => i.status === 'ok').length > 0 && (
        <Link to="/insights" style={{ textDecoration: 'none', color: 'inherit' }}>
          <div className="card" style={{ marginTop: 12 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
              <span className="text-title">Insights</span>
              <ChevronRight size={16} color="var(--muted)" />
            </div>
            {correlations.insights.filter(i => i.status === 'ok').slice(0, 2).map((ins, i) => (
              <div key={i} style={{ padding: '8px 0', borderTop: i > 0 ? '1px solid var(--border)' : undefined }}>
                <div className="text-body">{ins.title}</div>
                <div className="text-caption">{ins.summary}</div>
              </div>
            ))}
          </div>
        </Link>
      )}

      {/* Readiness */}
      {dash?.readiness && (
        <div className="card" style={{ marginTop: 12 }}>
          <div className="text-title" style={{ marginBottom: 8 }}>Readiness</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
            <div style={{
              width: 10, height: 10, borderRadius: '50%',
              background: dash.readiness.status === 'green' ? 'var(--green)'
                : dash.readiness.status === 'amber' ? 'var(--amber)'
                : dash.readiness.status === 'red' ? 'var(--red)'
                : 'var(--muted)',
            }} />
            <span className="text-body" style={{ fontWeight: 600, textTransform: 'capitalize' }}>
              {dash.readiness.status}
            </span>
            {dash.readiness.score != null && (
              <span className="text-caption">({dash.readiness.score}/100)</span>
            )}
          </div>
          {dash.readiness.components?.map((c, i) => (
            <div key={i} className="text-caption" style={{ padding: '2px 0' }}>
              • {c.name}: {c.value} ({c.status})
            </div>
          ))}
        </div>
      )}

      {/* Metric Drill-Downs */}
      {drillDown && (
        <MetricDrillDown
          open={!!drillDown}
          onClose={() => setDrillDown(null)}
          title={METRIC_DEFS[drillDown]?.label || drillDown}
          value={today ? getMetricValue(today, drillDown)?.toString() : undefined}
        >
          {/* Drill-down content is implemented in Task 5 */}
          <div className="text-caption">Detailed view coming soon</div>
        </MetricDrillDown>
      )}
    </div>
  )
}
```

- [ ] **Step 5: Restyle SyncStatusCard**

Update `frontend/src/components/SyncStatusCard.tsx` to use new design system classes and Lucide icons instead of emoji/text styling. Replace the outer container with a `.card` that has `borderLeft: 3px solid var(--amber)` for visual emphasis. Use `AlertTriangle` from lucide-react for the warning icon.

- [ ] **Step 6: Verify build and test dashboard**

```bash
cd frontend && npm run build
```

Expected: Build succeeds. Dashboard renders metrics row, activities, log summary, trends, insights, readiness.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: redesign dashboard with customizable metrics row, activities, trends"
```

---

### Task 5: Metric Drill-Down Content

**Files:**
- Create: `frontend/src/components/drilldowns/SleepDrillDown.tsx` — sleep stages, overnight HRV, score chart
- Create: `frontend/src/components/drilldowns/WeightDrillDown.tsx` — weight trend, TDEE, goal ETA, energy balance
- Create: `frontend/src/components/drilldowns/HrvDrillDown.tsx` — HRV trend, day-of-week pattern
- Create: `frontend/src/components/drilldowns/GenericDrillDown.tsx` — fallback for steps, calories burned, resting HR, body battery
- Modify: `frontend/src/pages/Dashboard.tsx` — wire drill-down content into MetricDrillDown
- Delete: `frontend/src/pages/SleepPage.tsx` — absorbed into drill-down
- Delete: `frontend/src/pages/WeightEnergyPage.tsx` — absorbed into drill-down

**Interfaces:**
- Consumes: `MetricDrillDown` from Task 4. `SleepRow`, `WeightTrendPoint`, `EnergyBalanceDay`, `Dashboard` types. `apiGet`, `useQuery`, `RangePicker`, `ChartCard`.
- Produces: Four drill-down content components, each receiving `days: number` and rendering charts + summary stats + history table.

- [ ] **Step 1: Create GenericDrillDown component**

Create `frontend/src/components/drilldowns/GenericDrillDown.tsx`:

```tsx
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip } from 'recharts'
import { apiGet } from '../../api/client'
import type { Dashboard } from '../../api/types'
import RangePicker from '../RangePicker'
import SkeletonLoader from '../SkeletonLoader'

export default function GenericDrillDown({ metricKey, unit }: { metricKey: string, unit?: string }) {
  const [days, setDays] = useState(30)
  const { data, isLoading } = useQuery<Dashboard>({
    queryKey: ['dashboard', days],
    queryFn: () => apiGet(`/api/analytics/dashboard?days=${days}`),
  })

  const chartData = data?.days
    ?.map(d => ({
      date: d.date.slice(5),
      value: (d as any)[metricKey] as number | null,
    }))
    .filter(d => d.value != null) || []

  const values = chartData.map(d => d.value!).filter(v => v != null)
  const avg = values.length ? Math.round(values.reduce((a, b) => a + b, 0) / values.length) : null
  const latest = values[values.length - 1] ?? null
  const avg7 = values.slice(-7)
  const avg7val = avg7.length ? Math.round(avg7.reduce((a, b) => a + b, 0) / avg7.length) : null
  const avg30 = values.slice(-30)
  const avg30val = avg30.length ? Math.round(avg30.reduce((a, b) => a + b, 0) / avg30.length) : null

  return (
    <div>
      {/* Summary row */}
      <div style={{ display: 'flex', gap: 16, marginBottom: 16 }}>
        <div>
          <div className="text-caption">Today</div>
          <div className="text-body" style={{ fontWeight: 600 }}>{latest ?? '–'}{unit ? ` ${unit}` : ''}</div>
        </div>
        <div>
          <div className="text-caption">7d avg</div>
          <div className="text-body" style={{ fontWeight: 600 }}>{avg7val ?? '–'}{unit ? ` ${unit}` : ''}</div>
        </div>
        <div>
          <div className="text-caption">30d avg</div>
          <div className="text-body" style={{ fontWeight: 600 }}>{avg30val ?? '–'}{unit ? ` ${unit}` : ''}</div>
        </div>
      </div>

      <RangePicker value={days} onChange={setDays} />

      {/* Chart */}
      {isLoading ? (
        <SkeletonLoader height="200px" borderRadius="14px" />
      ) : (
        <div style={{ marginTop: 12 }}>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={chartData}>
              <XAxis dataKey="date" tick={{ fill: 'var(--muted)', fontSize: 11 }} tickLine={false} axisLine={false} />
              <YAxis domain={['dataMin - 5', 'dataMax + 5']} tick={{ fill: 'var(--muted)', fontSize: 11 }} tickLine={false} axisLine={false} width={40} />
              <Tooltip contentStyle={{ background: 'var(--card-elevated)', border: '1px solid var(--border)', borderRadius: 8, color: 'var(--text)' }} />
              <Line type="monotone" dataKey="value" stroke="var(--accent)" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* History table */}
      <div style={{ marginTop: 16 }}>
        <div className="text-title" style={{ marginBottom: 8 }}>Recent</div>
        {chartData.slice(-14).reverse().map((d, i) => (
          <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid var(--border)' }}>
            <span className="text-body">{d.date}</span>
            <span className="text-body" style={{ fontWeight: 600 }}>{d.value}{unit ? ` ${unit}` : ''}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Create SleepDrillDown component**

Create `frontend/src/components/drilldowns/SleepDrillDown.tsx`:

```tsx
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  ResponsiveContainer, BarChart, Bar, LineChart, Line,
  XAxis, YAxis, Tooltip, Legend,
} from 'recharts'
import { apiGet } from '../../api/client'
import type { SleepRow } from '../../api/types'
import RangePicker from '../RangePicker'
import SkeletonLoader from '../SkeletonLoader'

export default function SleepDrillDown() {
  const [days, setDays] = useState(30)
  const { data: rows, isLoading } = useQuery<SleepRow[]>({
    queryKey: ['sleep', days],
    queryFn: () => apiGet(`/api/metrics/sleep?days=${days}`),
  })

  if (isLoading) return <SkeletonLoader height="400px" borderRadius="14px" />

  const data = (rows || []).map(r => ({
    date: r.date.slice(5),
    deep: +(r.deep_min / 60).toFixed(1),
    light: +(r.light_min / 60).toFixed(1),
    rem: +(r.rem_min / 60).toFixed(1),
    awake: +(r.awake_min / 60).toFixed(1),
    score: r.sleep_score,
    hrv: r.overnight_hrv,
    duration: +(r.duration_min / 60).toFixed(1),
  }))

  const latest = data[data.length - 1]
  const avgScore = data.length ? Math.round(data.reduce((s, d) => s + (d.score || 0), 0) / data.filter(d => d.score).length) : null
  const avgDuration = data.length ? (data.reduce((s, d) => s + d.duration, 0) / data.length).toFixed(1) : null

  return (
    <div>
      {/* Summary row */}
      <div style={{ display: 'flex', gap: 16, marginBottom: 16, flexWrap: 'wrap' }}>
        <div><div className="text-caption">Last Night</div><div className="text-body" style={{ fontWeight: 600 }}>{latest?.duration ?? '–'}h</div></div>
        <div><div className="text-caption">Score</div><div className="text-body" style={{ fontWeight: 600 }}>{latest?.score ?? '–'}</div></div>
        <div><div className="text-caption">Avg Score</div><div className="text-body" style={{ fontWeight: 600 }}>{avgScore ?? '–'}</div></div>
        <div><div className="text-caption">Avg Duration</div><div className="text-body" style={{ fontWeight: 600 }}>{avgDuration ?? '–'}h</div></div>
        <div><div className="text-caption">Deep</div><div className="text-body" style={{ fontWeight: 600 }}>{latest ? `${Math.round(latest.deep * 60)}m` : '–'}</div></div>
        <div><div className="text-caption">REM</div><div className="text-body" style={{ fontWeight: 600 }}>{latest ? `${Math.round(latest.rem * 60)}m` : '–'}</div></div>
      </div>

      <RangePicker value={days} onChange={setDays} />

      {/* Sleep stages stacked bar */}
      <div className="text-title" style={{ margin: '16px 0 8px' }}>Sleep Stages</div>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={data}>
          <XAxis dataKey="date" tick={{ fill: 'var(--muted)', fontSize: 11 }} tickLine={false} axisLine={false} />
          <YAxis tick={{ fill: 'var(--muted)', fontSize: 11 }} tickLine={false} axisLine={false} width={30} />
          <Tooltip contentStyle={{ background: 'var(--card-elevated)', border: '1px solid var(--border)', borderRadius: 8, color: 'var(--text)' }} />
          <Legend wrapperStyle={{ fontSize: 11, color: 'var(--muted)' }} />
          <Bar dataKey="deep" stackId="a" fill="#6366f1" name="Deep" radius={[0, 0, 0, 0]} />
          <Bar dataKey="light" stackId="a" fill="#38bdf8" name="Light" />
          <Bar dataKey="rem" stackId="a" fill="#a78bfa" name="REM" />
          <Bar dataKey="awake" stackId="a" fill="#f87171" name="Awake" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>

      {/* Sleep score line */}
      <div className="text-title" style={{ margin: '16px 0 8px' }}>Sleep Score</div>
      <ResponsiveContainer width="100%" height={150}>
        <LineChart data={data}>
          <XAxis dataKey="date" tick={{ fill: 'var(--muted)', fontSize: 11 }} tickLine={false} axisLine={false} />
          <YAxis domain={[0, 100]} tick={{ fill: 'var(--muted)', fontSize: 11 }} tickLine={false} axisLine={false} width={30} />
          <Tooltip contentStyle={{ background: 'var(--card-elevated)', border: '1px solid var(--border)', borderRadius: 8, color: 'var(--text)' }} />
          <Line type="monotone" dataKey="score" stroke="var(--accent)" strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>

      {/* Overnight HRV */}
      {data.some(d => d.hrv) && (
        <>
          <div className="text-title" style={{ margin: '16px 0 8px' }}>Overnight HRV</div>
          <ResponsiveContainer width="100%" height={150}>
            <LineChart data={data.filter(d => d.hrv)}>
              <XAxis dataKey="date" tick={{ fill: 'var(--muted)', fontSize: 11 }} tickLine={false} axisLine={false} />
              <YAxis tick={{ fill: 'var(--muted)', fontSize: 11 }} tickLine={false} axisLine={false} width={30} />
              <Tooltip contentStyle={{ background: 'var(--card-elevated)', border: '1px solid var(--border)', borderRadius: 8, color: 'var(--text)' }} />
              <Line type="monotone" dataKey="hrv" stroke="var(--green)" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </>
      )}
    </div>
  )
}
```

- [ ] **Step 3: Create WeightDrillDown component**

Create `frontend/src/components/drilldowns/WeightDrillDown.tsx`:

```tsx
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  ResponsiveContainer, LineChart, Line, BarChart, Bar,
  XAxis, YAxis, Tooltip, ReferenceLine,
} from 'recharts'
import { apiGet } from '../../api/client'
import type { WeightTrendPoint, EnergyBalanceDay, TdeeResult } from '../../api/types'
import RangePicker from '../RangePicker'
import SkeletonLoader from '../SkeletonLoader'

export default function WeightDrillDown() {
  const [days, setDays] = useState(90)
  const { data: trend, isLoading: trendLoading } = useQuery<WeightTrendPoint[]>({
    queryKey: ['weight-trend', days],
    queryFn: () => apiGet(`/api/weight/trend?days=${days}`),
  })
  const { data: energy } = useQuery<EnergyBalanceDay[]>({
    queryKey: ['energy', days],
    queryFn: () => apiGet(`/api/analytics/energy-balance?days=${days}`),
  })
  const { data: tdee } = useQuery<TdeeResult>({
    queryKey: ['tdee'],
    queryFn: () => apiGet('/api/analytics/tdee'),
  })

  if (trendLoading) return <SkeletonLoader height="400px" borderRadius="14px" />

  const trendData = (trend || []).map(p => ({
    date: p.date.slice(5),
    weight: p.weight,
    trend: p.trend ? +p.trend.toFixed(1) : null,
  }))

  const latest = trendData[trendData.length - 1]
  const trendSlope = trend && trend.length >= 14
    ? +((trend[trend.length - 1].trend! - trend[Math.max(0, trend.length - 8)].trend!) / (7 / (trend.length > 8 ? trend.length - (trend.length - 8) : trend.length)) ).toFixed(2)
    : null

  const energyData = (energy || []).map(d => ({
    date: d.date.slice(5),
    balance: d.valid ? d.balance : null,
    invalid: !d.valid,
  }))

  return (
    <div>
      {/* Summary */}
      <div style={{ display: 'flex', gap: 16, marginBottom: 16, flexWrap: 'wrap' }}>
        <div><div className="text-caption">Current</div><div className="text-body" style={{ fontWeight: 600 }}>{latest?.weight ?? '–'} kg</div></div>
        <div><div className="text-caption">Trend</div><div className="text-body" style={{ fontWeight: 600 }}>{latest?.trend ?? '–'} kg</div></div>
        {tdee?.tdee && <div><div className="text-caption">TDEE</div><div className="text-body" style={{ fontWeight: 600 }}>{Math.round(tdee.tdee)} kcal</div></div>}
        {trendSlope != null && <div><div className="text-caption">Trend/wk</div><div className="text-body" style={{ fontWeight: 600, color: trendSlope < 0 ? 'var(--green)' : trendSlope > 0 ? 'var(--red)' : 'var(--muted)' }}>{trendSlope > 0 ? '+' : ''}{trendSlope} kg</div></div>}
      </div>

      <RangePicker value={days} onChange={setDays} />

      {/* Weight chart */}
      <div className="text-title" style={{ margin: '16px 0 8px' }}>Weight Trend</div>
      <ResponsiveContainer width="100%" height={200}>
        <LineChart data={trendData}>
          <XAxis dataKey="date" tick={{ fill: 'var(--muted)', fontSize: 11 }} tickLine={false} axisLine={false} />
          <YAxis domain={['dataMin - 1', 'dataMax + 1']} tick={{ fill: 'var(--muted)', fontSize: 11 }} tickLine={false} axisLine={false} width={40} />
          <Tooltip contentStyle={{ background: 'var(--card-elevated)', border: '1px solid var(--border)', borderRadius: 8, color: 'var(--text)' }} />
          <Line type="monotone" dataKey="weight" stroke="var(--muted)" strokeWidth={1} dot={{ r: 2, fill: 'var(--muted)' }} name="Weight" />
          <Line type="monotone" dataKey="trend" stroke="var(--accent)" strokeWidth={2} dot={false} name="Trend" />
        </LineChart>
      </ResponsiveContainer>

      {/* Energy balance */}
      {energyData.length > 0 && (
        <>
          <div className="text-title" style={{ margin: '16px 0 8px' }}>Energy Balance</div>
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={energyData}>
              <XAxis dataKey="date" tick={{ fill: 'var(--muted)', fontSize: 11 }} tickLine={false} axisLine={false} />
              <YAxis tick={{ fill: 'var(--muted)', fontSize: 11 }} tickLine={false} axisLine={false} width={40} />
              <ReferenceLine y={0} stroke="var(--border)" />
              <Tooltip contentStyle={{ background: 'var(--card-elevated)', border: '1px solid var(--border)', borderRadius: 8, color: 'var(--text)' }} />
              <Bar dataKey="balance" fill="var(--accent)"
                shape={(props: any) => {
                  const { x, y, width, height, payload } = props
                  const fill = payload.invalid ? 'var(--border)' : payload.balance > 0 ? 'var(--red)' : 'var(--green)'
                  return <rect x={x} y={y} width={width} height={Math.abs(height)} fill={fill} rx={2} />
                }}
              />
            </BarChart>
          </ResponsiveContainer>
        </>
      )}
    </div>
  )
}
```

- [ ] **Step 4: Create HrvDrillDown component**

Create `frontend/src/components/drilldowns/HrvDrillDown.tsx`:

```tsx
import GenericDrillDown from './GenericDrillDown'

export default function HrvDrillDown() {
  return <GenericDrillDown metricKey="hrv" unit="ms" />
}
```

Note: This starts simple. The day-of-week pattern chart can be added as a follow-up enhancement — the generic drill-down already provides the core value (trend chart + summary + history).

- [ ] **Step 5: Wire drill-downs into Dashboard**

In `frontend/src/pages/Dashboard.tsx`, replace the placeholder drill-down content:

```tsx
// Add imports at top:
import SleepDrillDown from '../components/drilldowns/SleepDrillDown'
import WeightDrillDown from '../components/drilldowns/WeightDrillDown'
import HrvDrillDown from '../components/drilldowns/HrvDrillDown'
import GenericDrillDown from '../components/drilldowns/GenericDrillDown'

// Replace the MetricDrillDown children block with:
{drillDown === 'sleep_score' && <SleepDrillDown />}
{drillDown === 'hrv' && <HrvDrillDown />}
{drillDown === 'weight' && <WeightDrillDown />}
{drillDown === 'calories_out' && <GenericDrillDown metricKey="calories_out" unit="kcal" />}
{drillDown === 'steps' && <GenericDrillDown metricKey="steps" />}
{drillDown === 'resting_hr' && <GenericDrillDown metricKey="resting_hr" unit="bpm" />}
{drillDown === 'body_battery' && <GenericDrillDown metricKey="body_battery" />}
```

- [ ] **Step 6: Delete SleepPage and WeightEnergyPage**

Delete `frontend/src/pages/SleepPage.tsx` and `frontend/src/pages/WeightEnergyPage.tsx`. Remove their route entries from `App.tsx` (already removed in Task 3) and any remaining imports.

- [ ] **Step 7: Verify build**

```bash
cd frontend && npm run build
```

Expected: Build succeeds. Tapping any metric card on dashboard opens the drill-down view with charts.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat: metric drill-down views for sleep, weight, HRV, and generic metrics"
```

---

### Task 6: Log Tab Redesign

**Files:**
- Rewrite: `frontend/src/pages/LogPage.tsx` — new layout with check-in sheet, nutrition summary, quick actions
- Modify: `frontend/src/components/MealCard.tsx` — restyle, integrate SwipeToDelete
- Modify: `frontend/src/components/StreakWeekRow.tsx` — restyle with new design system
- Modify: `frontend/src/components/CalorieDonut.tsx` — restyle
- Modify: `frontend/src/components/ProgressBar.tsx` — restyle
- Delete: `frontend/src/pages/CheckinPage.tsx` — absorbed into bottom sheet
- Delete: `frontend/src/pages/OtherLogsPage.tsx` — absorbed into Log tab quick actions

**Interfaces:**
- Consumes: `BottomSheet`, `SwipeToDelete` from Task 2. `Stepper`, `CalorieDonut`, `StreakWeekRow`, `ProgressBar` components. API types: `Checkin`, `CheckinResponse`, `FoodLogRow`, `StreakInfo`, `Meal`.
- Produces: Redesigned `LogPage` with inline check-in bottom sheet and quick action sheets.

- [ ] **Step 1: Create the check-in bottom sheet content**

Add check-in form as inline content within `LogPage.tsx` using the `BottomSheet` component. The check-in sheet renders: mood emoji row (5 buttons), alcohol `Stepper`, caffeine `Stepper` + time picker (if > 0), illness toggle chips, weight input, eating window time inputs, note textarea, and save button. Use the same form state and mutation logic currently in `CheckinPage.tsx` but rendered inside a `<BottomSheet open={showCheckin} onClose={() => setShowCheckin(false)} title="Daily Check-in">`.

- [ ] **Step 2: Restyle MealCard with SwipeToDelete**

Update `frontend/src/components/MealCard.tsx`:
- Replace the delete X buttons on individual food entries with `<SwipeToDelete onDelete={() => onDelete(entry.id)}>` wrapping each entry row.
- Use Lucide icons for meal type (e.g. `Coffee` for breakfast, `Sun` for lunch, `Moon` for dinner, `Cookie` for snack) instead of emoji.
- Apply new typography classes.

- [ ] **Step 3: Restyle StreakWeekRow, CalorieDonut, ProgressBar**

Update each component to use the new color palette variables and typography:
- `StreakWeekRow`: Use `Flame` icon from lucide-react instead of emoji. Update dot colors to `--green`, `--amber`, `--border`.
- `CalorieDonut`: Update segment colors to use CSS variables. Update center text to `text-display` sizing.
- `ProgressBar`: Update track color to `--border`, fill to use the passed color prop or `--accent` default, over-target to `--red`.

- [ ] **Step 4: Rewrite LogPage**

Rewrite `frontend/src/pages/LogPage.tsx` with the new layout:

```tsx
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
  ChevronLeft, ChevronRight, Plus, Utensils, Scale,
  StickyNote, RefreshCw,
} from 'lucide-react'
import { format, addDays, subDays, isToday } from 'date-fns'
import { apiGet, apiPost, apiPut, apiDelete } from '../api/client'
import type {
  FoodLogRow, Checkin, CheckinResponse, StreakInfo, Meal, MfpStatus,
} from '../api/types'
import BottomSheet from '../components/BottomSheet'
import SwipeToDelete from '../components/SwipeToDelete'
import CalorieDonut from '../components/CalorieDonut'
import ProgressBar from '../components/ProgressBar'
import StreakWeekRow from '../components/StreakWeekRow'
import MealCard from '../components/MealCard'
import Stepper from '../components/Stepper'

const MEALS: Meal[] = ['breakfast', 'lunch', 'dinner', 'snack']

export default function LogPage() {
  const qc = useQueryClient()
  const [date, setDate] = useState(() => format(new Date(), 'yyyy-MM-dd'))
  const [showCheckin, setShowCheckin] = useState(false)
  const [showQuickAdd, setShowQuickAdd] = useState(false)
  const [showWeightLog, setShowWeightLog] = useState(false)
  const [showNote, setShowNote] = useState(false)

  // --- Queries (same API endpoints as current LogPage) ---
  const { data: foodLog } = useQuery<FoodLogRow[]>({
    queryKey: ['food-log', date],
    queryFn: () => apiGet(`/api/food/log?date=${date}`),
  })
  const { data: checkinResp } = useQuery<CheckinResponse>({
    queryKey: ['checkin', date],
    queryFn: () => apiGet(`/api/context/checkin/${date}`),
  })
  const { data: streak } = useQuery<StreakInfo>({
    queryKey: ['streak'],
    queryFn: () => apiGet('/api/context/streak'),
  })
  const { data: targets } = useQuery<{ calorie_target: number, protein_g: number, carbs_g: number, fat_g: number }>({
    queryKey: ['targets'],
    queryFn: () => apiGet('/api/settings/targets'),
  })
  const { data: mfpStatus } = useQuery<MfpStatus>({
    queryKey: ['mfp-status'],
    queryFn: () => apiGet('/api/mfp/status'),
  })

  const deleteFoodMut = useMutation({
    mutationFn: (id: number) => apiDelete(`/api/food/log/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['food-log', date] }),
  })

  const mfpSyncMut = useMutation({
    mutationFn: () => apiPost('/api/mfp/sync'),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['food-log'] }),
  })

  // --- Computed values ---
  const meals = MEALS.map(m => ({
    meal: m,
    entries: (foodLog || []).filter(f => f.meal === m),
  }))
  const totalCal = (foodLog || []).reduce((s, f) => s + (f.kcal || 0), 0)
  const totalP = (foodLog || []).reduce((s, f) => s + (f.protein_g || 0), 0)
  const totalC = (foodLog || []).reduce((s, f) => s + (f.carbs_g || 0), 0)
  const totalF = (foodLog || []).reduce((s, f) => s + (f.fat_g || 0), 0)
  const isDateToday = isToday(new Date(date + 'T00:00:00'))
  const checkin = checkinResp?.checkin

  function prevDay() { setDate(format(subDays(new Date(date + 'T00:00:00'), 1), 'yyyy-MM-dd')) }
  function nextDay() {
    if (!isDateToday) setDate(format(addDays(new Date(date + 'T00:00:00'), 1), 'yyyy-MM-dd'))
  }

  return (
    <div style={{ padding: '16px' }}>
      {/* Date bar */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 16, marginBottom: 12 }}>
        <button onClick={prevDay} className="header-btn"><ChevronLeft size={20} /></button>
        <span className="text-title">{isDateToday ? 'Today' : date}</span>
        <button onClick={nextDay} className="header-btn" disabled={isDateToday}><ChevronRight size={20} /></button>
      </div>

      {/* Streak */}
      {streak && <StreakWeekRow streak={streak} />}

      {/* Check-in card */}
      <div className="card" style={{ marginTop: 12 }}>
        {checkin ? (
          <div onClick={() => setShowCheckin(true)} style={{ cursor: 'pointer' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
              <span className="text-title">Check-in</span>
              <span className="text-caption" style={{ color: 'var(--accent)' }}>Edit</span>
            </div>
            <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
              {checkin.mood && <span className="text-body">{['', '😫', '😕', '😐', '🙂', '😄'][checkin.mood]}</span>}
              {checkin.alcohol_units > 0 && <span className="text-caption">🍺 {checkin.alcohol_units}</span>}
              {checkin.caffeine_cups > 0 && <span className="text-caption">☕ {checkin.caffeine_cups}</span>}
              {checkin.illness && <span className="text-caption">🤒 Ill</span>}
              {checkinResp?.eating_window && <span className="text-caption">🍽️ {checkinResp.eating_window}</span>}
            </div>
          </div>
        ) : (
          <div>
            <div className="text-title" style={{ marginBottom: 8 }}>How's your day?</div>
            <button
              onClick={() => setShowCheckin(true)}
              style={{ width: '100%', padding: '12px', borderRadius: 10, background: 'var(--accent)', color: 'white', border: 'none', fontWeight: 600 }}
            >
              Check in
            </button>
          </div>
        )}
      </div>

      {/* Nutrition summary */}
      <div className="card" style={{ marginTop: 12 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <span className="text-title">Nutrition</span>
          {mfpStatus?.status === 'connected' && (
            <span className="text-caption" style={{ color: 'var(--green)' }}>via MFP</span>
          )}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <CalorieDonut calories={totalCal} protein_g={totalP} carbs_g={totalC} fat_g={totalF} size={90} />
          <div style={{ flex: 1 }}>
            <div style={{ marginBottom: 8 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span className="text-caption">Calories</span>
                <span className="text-caption">{totalCal} / {targets?.calorie_target ?? '–'}</span>
              </div>
              <ProgressBar value={totalCal} target={targets?.calorie_target ?? 2000} color="var(--accent)" />
            </div>
            <div style={{ marginBottom: 6 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span className="text-caption">Protein</span>
                <span className="text-caption">{totalP}g / {targets?.protein_g ?? '–'}g</span>
              </div>
              <ProgressBar value={totalP} target={targets?.protein_g ?? 150} color="var(--green)" />
            </div>
            <div style={{ marginBottom: 6 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span className="text-caption">Carbs</span>
                <span className="text-caption">{totalC}g / {targets?.carbs_g ?? '–'}g</span>
              </div>
              <ProgressBar value={totalC} target={targets?.carbs_g ?? 200} color="var(--amber)" />
            </div>
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span className="text-caption">Fat</span>
                <span className="text-caption">{totalF}g / {targets?.fat_g ?? '–'}g</span>
              </div>
              <ProgressBar value={totalF} target={targets?.fat_g ?? 65} color="#a78bfa" />
            </div>
          </div>
        </div>
      </div>

      {/* Quick actions */}
      <div style={{ display: 'flex', gap: 8, marginTop: 12, overflowX: 'auto' }}>
        {mfpStatus?.status === 'connected' && (
          <button className="chip" onClick={() => mfpSyncMut.mutate()} disabled={mfpSyncMut.isPending}>
            <RefreshCw size={14} /> Sync MFP
          </button>
        )}
        <button className="chip" onClick={() => setShowQuickAdd(true)}>
          <Plus size={14} /> Quick add
        </button>
        <button className="chip" onClick={() => setShowWeightLog(true)}>
          <Scale size={14} /> Weight
        </button>
        <button className="chip" onClick={() => setShowNote(true)}>
          <StickyNote size={14} /> Note
        </button>
      </div>

      {/* Meal cards */}
      {meals.map(({ meal, entries }) => (
        <MealCard
          key={meal}
          meal={meal}
          entries={entries}
          onLog={() => {/* navigate to food log */}}
          onDelete={(id) => deleteFoodMut.mutate(id)}
          onEdit={() => {}}
        />
      ))}

      {/* Check-in bottom sheet */}
      <BottomSheet open={showCheckin} onClose={() => setShowCheckin(false)} title="Daily Check-in">
        {/* Check-in form content — move the form logic from CheckinPage.tsx here.
            Same fields: mood (5 emoji buttons), alcohol Stepper, caffeine Stepper + time,
            illness toggle, weight input, eating window times, note textarea, save button.
            Use the same mutation: apiPost/apiPut to /api/context/checkin.
            On save success: invalidate ['checkin', date], close sheet. */}
        <div style={{ padding: '8px 0 16px' }}>
          <p className="text-caption">Check-in form — port the form body from CheckinPage.tsx here</p>
        </div>
      </BottomSheet>

      {/* Quick add bottom sheet */}
      <BottomSheet open={showQuickAdd} onClose={() => setShowQuickAdd(false)} title="Quick Add Food">
        {/* Name input + kcal input + optional meal selector + save button.
            Mutation: apiPost to /api/food/log with { name, kcal, meal, date }. */}
        <div style={{ padding: '8px 0 16px' }}>
          <p className="text-caption">Quick add form</p>
        </div>
      </BottomSheet>

      {/* Weight log bottom sheet */}
      <BottomSheet open={showWeightLog} onClose={() => setShowWeightLog(false)} title="Log Weight">
        {/* Weight input (kg) + note + save button.
            Mutation: apiPost to /api/weight with { weight_kg, note, date }. */}
        <div style={{ padding: '8px 0 16px' }}>
          <p className="text-caption">Weight log form</p>
        </div>
      </BottomSheet>

      {/* Note bottom sheet */}
      <BottomSheet open={showNote} onClose={() => setShowNote(false)} title="Add Note">
        {/* Note textarea + save button.
            Mutation: apiPost to /api/context with { type: 'note', note, date }. */}
        <div style={{ padding: '8px 0 16px' }}>
          <p className="text-caption">Note form</p>
        </div>
      </BottomSheet>
    </div>
  )
}
```

**Important implementation note for the executing agent:** The bottom sheet form bodies are outlined above with their API contract. The executing agent MUST port the full form logic from `CheckinPage.tsx` into the check-in sheet, and create working forms for quick-add, weight, and note sheets. The placeholder `<p>` tags are structural markers — replace them with actual form elements using the same patterns as the existing `CheckinPage.tsx` (Stepper, mood buttons, etc.).

- [ ] **Step 5: Delete CheckinPage and OtherLogsPage**

Delete `frontend/src/pages/CheckinPage.tsx` and `frontend/src/pages/OtherLogsPage.tsx`. Remove their route entries from `App.tsx` (remove `/log/checkin` and `/log/other` routes).

- [ ] **Step 6: Verify build**

```bash
cd frontend && npm run build
```

Expected: Build succeeds. Log tab shows date bar, streak, check-in card, nutrition summary, quick actions, meal cards.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: redesign Log tab with check-in sheet, nutrition summary, quick actions"
```

---

### Task 7: Workouts Tab Restyle & Active Workout UX Fixes

**Files:**
- Modify: `frontend/src/pages/WorkoutsPage.tsx` — restyle with new design system and Lucide icons
- Modify: `frontend/src/pages/ActiveWorkoutPage.tsx` — fix sync overlap, exercise search, tap-to-edit, swipe-to-delete, custom timer, mid-workout stats
- Modify: `frontend/src/components/ExercisePicker.tsx` — full-screen sheet with fixed search bar
- Modify: `frontend/src/components/RestTimerBar.tsx` — add custom seconds input
- Modify: `frontend/src/pages/WorkoutDetailPage.tsx` — restyle
- Modify: `frontend/src/pages/WorkoutSummaryPage.tsx` — restyle
- Modify: `frontend/src/pages/ExerciseStatsPage.tsx` — restyle
- Modify: `frontend/src/pages/RoutinesPage.tsx` — restyle

**Interfaces:**
- Consumes: `SwipeToDelete`, `BottomSheet` from Task 2. Existing workout API types and endpoints.
- Produces: Restyled workout pages with all 7 UX fixes applied.

- [ ] **Step 1: Restyle WorkoutsPage**

Update `frontend/src/pages/WorkoutsPage.tsx`:
- Replace emoji activity type icons with Lucide icons: `Run` for running, `Bike` for cycling, `Waves` for swimming, `Dumbbell` for strength, `Activity` as default.
- Replace `.chip` tab styling to use new design system colors.
- Wrap workout history cards in `SwipeToDelete` with `onDelete` calling the existing delete mutation.
- Update "Start Workout" button: full-width, accent background, 14px border-radius, `Dumbbell` icon.
- Update "Routines" button: secondary style next to start button.
- Apply `text-title`, `text-body`, `text-caption` classes throughout.

- [ ] **Step 2: Fix ExercisePicker — full-screen sheet with fixed search**

Rewrite `frontend/src/components/ExercisePicker.tsx`:

```tsx
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Search, X, Plus } from 'lucide-react'
import { apiGet, apiPost } from '../api/client'
import type { Exercise } from '../api/types'

export default function ExercisePicker({
  onPick,
  onClose,
}: {
  onPick: (ex: Exercise) => void
  onClose: () => void
}) {
  const [q, setQ] = useState('')
  const [showCreate, setShowCreate] = useState(false)
  const [newName, setNewName] = useState('')
  const [newCategory, setNewCategory] = useState('strength')
  const [newMuscles, setNewMuscles] = useState<string[]>([])
  const qc = useQueryClient()

  const { data: exercises } = useQuery<Exercise[]>({
    queryKey: ['exercises'],
    queryFn: () => apiGet('/api/workouts/exercises'),
  })

  const createMut = useMutation({
    mutationFn: (body: { name: string, category: string, primary_muscles: string[] }) =>
      apiPost<Exercise>('/api/workouts/exercises', body),
    onSuccess: (ex) => {
      qc.invalidateQueries({ queryKey: ['exercises'] })
      onPick(ex)
    },
  })

  const filtered = (exercises || []).filter(e =>
    e.name.toLowerCase().includes(q.toLowerCase())
  )

  const MUSCLES = ['chest', 'back', 'shoulders', 'biceps', 'triceps', 'forearms',
    'quads', 'hamstrings', 'glutes', 'calves', 'abs', 'traps', 'lats']

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'var(--bg)', zIndex: 200,
      display: 'flex', flexDirection: 'column',
    }}>
      {/* Fixed header with search */}
      <div style={{
        padding: '16px', paddingTop: 'calc(16px + env(safe-area-inset-top))',
        borderBottom: '1px solid var(--border)', background: 'var(--bg)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12 }}>
          <button onClick={onClose} className="header-btn" aria-label="Close"><X size={20} /></button>
          <span className="text-title">Add Exercise</span>
        </div>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 8,
          background: 'var(--card)', borderRadius: 10, padding: '10px 12px',
        }}>
          <Search size={16} color="var(--muted)" />
          <input
            type="text"
            placeholder="Search exercises..."
            value={q}
            onChange={e => setQ(e.target.value)}
            autoFocus
            style={{
              flex: 1, background: 'none', border: 'none', color: 'var(--text)',
              fontSize: '0.9rem', outline: 'none',
            }}
          />
        </div>
      </div>

      {/* Scrollable results */}
      <div style={{ flex: 1, overflowY: 'auto', WebkitOverflowScrolling: 'touch', padding: '8px 16px' }}>
        {!showCreate ? (
          <>
            {filtered.map(ex => (
              <button
                key={ex.id}
                onClick={() => onPick(ex)}
                style={{
                  display: 'block', width: '100%', textAlign: 'left', padding: '14px 0',
                  borderBottom: '1px solid var(--border)', background: 'none', border: 'none',
                  borderBottomStyle: 'solid', borderBottomWidth: 1, borderBottomColor: 'var(--border)',
                  color: 'var(--text)',
                }}
              >
                <div className="text-body">{ex.name}</div>
                <div className="text-caption">{ex.category} · {ex.primary_muscles?.join(', ')}</div>
              </button>
            ))}
            <button
              onClick={() => setShowCreate(true)}
              style={{
                display: 'flex', alignItems: 'center', gap: 8, width: '100%',
                padding: '14px 0', background: 'none', border: 'none', color: 'var(--accent)',
              }}
            >
              <Plus size={18} /> Create new exercise
            </button>
          </>
        ) : (
          <div style={{ paddingTop: 8 }}>
            <input
              placeholder="Exercise name"
              value={newName}
              onChange={e => setNewName(e.target.value)}
              style={{ width: '100%', marginBottom: 12 }}
            />
            <select value={newCategory} onChange={e => setNewCategory(e.target.value)} style={{ width: '100%', marginBottom: 12 }}>
              <option value="strength">Strength</option>
              <option value="cardio">Cardio</option>
              <option value="flexibility">Flexibility</option>
            </select>
            <div className="text-caption" style={{ marginBottom: 8 }}>Primary muscles:</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 16 }}>
              {MUSCLES.map(m => (
                <button
                  key={m}
                  className={`chip ${newMuscles.includes(m) ? 'active' : ''}`}
                  onClick={() => setNewMuscles(prev =>
                    prev.includes(m) ? prev.filter(x => x !== m) : [...prev, m]
                  )}
                  style={{ fontSize: '0.75rem', padding: '6px 10px' }}
                >
                  {m}
                </button>
              ))}
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <button className="secondary" onClick={() => setShowCreate(false)} style={{ flex: 1 }}>Cancel</button>
              <button
                onClick={() => createMut.mutate({ name: newName, category: newCategory, primary_muscles: newMuscles })}
                disabled={!newName.trim()}
                style={{ flex: 1 }}
              >
                Create
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Fix ActiveWorkoutPage — sync overlap, tap-to-edit, swipe-to-delete**

Modify `frontend/src/pages/ActiveWorkoutPage.tsx`:

1. **Header**: Replace the current header with a workout-specific header showing elapsed timer (left), workout name (center), "Finish" button (right, accent color). No sync button renders because `GlobalSyncButton` already hides via the `isActiveWorkout` check in `App.tsx`.

2. **Tap-to-edit sets**: When a logged set is tapped, toggle it into edit mode. Add a state `editingSet: number | null`. When `editingSet === setIndex`, render editable inputs for weight/reps/RPE instead of static text. On blur or "Save" tap, call the existing update mutation and clear `editingSet`.

3. **Swipe-to-delete**: Wrap each `.set-row` in `<SwipeToDelete onDelete={() => deleteSet(setIndex)}>`. Wrap each `.exercise-card` header in `<SwipeToDelete onDelete={() => removeExercise(exIndex)} confirm>`.

4. **Exercise stats mid-workout**: Make the exercise name a tappable link. On tap, open a `<BottomSheet>` that queries `/api/workouts/stats/${exerciseId}` and shows: last 3 sessions as a compact list (date, sets notation), best e1RM with PR badge, and a mini line chart of e1RM progression.

- [ ] **Step 4: Add custom seconds input to RestTimerBar**

Modify `frontend/src/components/RestTimerBar.tsx`:
- In the config section (where preset buttons 60/90/120/180 are), add a number input after the presets:

```tsx
<input
  type="number"
  placeholder="Custom"
  min={0}
  max={600}
  style={{
    width: 72, textAlign: 'center', background: 'var(--card)',
    border: '1px solid var(--border)', borderRadius: 8,
    color: 'var(--text)', padding: '8px',
  }}
  onBlur={e => {
    const val = parseInt(e.target.value)
    if (val > 0) setConfigured(val)
  }}
/>
```

- [ ] **Step 5: Restyle WorkoutDetailPage, WorkoutSummaryPage, ExerciseStatsPage, RoutinesPage**

For each page:
- Replace emoji icons with Lucide equivalents.
- Apply `text-display`, `text-title`, `text-body`, `text-caption` classes.
- Update card styles to use new `--card`, `--border`, `--card-elevated` variables.
- Replace back link text (`‹ Back`) with `<ArrowLeft size={20} />` button.
- Apply `SwipeToDelete` where delete actions exist (routine exercises, workout sets).
- Ensure all `.metric-card` instances use the updated `MetricCard` component from Task 4.

- [ ] **Step 6: Verify build**

```bash
cd frontend && npm run build
```

Expected: Build succeeds. Workouts tab renders with new styles. Active workout has no sync button overlap, search opens full-screen, sets are tap-to-edit and swipe-to-delete.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: workouts tab restyle and active workout UX fixes"
```

---

### Task 8: Settings, AI, Bloodwork, Insights Restyle

**Files:**
- Modify: `frontend/src/pages/SettingsPage.tsx` — reorganize into Profile/Dashboard/Notifications/Integrations/Data sections
- Modify: `frontend/src/pages/AIPage.tsx` — restyle chat bubbles, report viewer
- Modify: `frontend/src/pages/BloodworkPage.tsx` — restyle with design system, bottom sheet for panel entry
- Modify: `frontend/src/pages/InsightsPage.tsx` — strength-colored left borders on cards
- Modify: `frontend/src/pages/FoodLogPage.tsx` — restyle with design system
- Modify: `frontend/src/pages/FoodDetailPage.tsx` — restyle with design system
- Modify: `frontend/src/index.css` — add chat bubble styles, insight card styles

**Interfaces:**
- Consumes: `BottomSheet` from Task 2. All existing API types and endpoints.
- Produces: Restyled pages matching the new design system.

- [ ] **Step 1: Add chat bubble and insight card styles to index.css**

```css
/* Chat bubbles */
.chat-msg {
  max-width: 85%;
  padding: 12px 16px;
  border-radius: 16px;
  margin-bottom: 8px;
  font-size: 0.9rem;
  line-height: 1.5;
}

.chat-msg.user {
  background: var(--accent);
  color: white;
  margin-left: auto;
  border-bottom-right-radius: 4px;
}

.chat-msg.assistant {
  background: var(--card);
  color: var(--text);
  margin-right: auto;
  border-bottom-left-radius: 4px;
}

/* Insight cards */
.insight-card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 16px;
  margin-bottom: 12px;
  border-left: 3px solid var(--muted);
}

.insight-card.strong { border-left-color: var(--red); }
.insight-card.moderate { border-left-color: var(--amber); }
.insight-card.weak { border-left-color: var(--accent); }
.insight-card.tentative { border-left-color: var(--accent); }
```

- [ ] **Step 2: Restyle AIPage**

Update `frontend/src/pages/AIPage.tsx`:
- Replace message rendering with `.chat-msg.user` and `.chat-msg.assistant` classes.
- Fix the input bar to the bottom of the viewport with proper safe area padding.
- Replace the send button icon with `Send` from lucide-react.
- Apply `text-title`, `text-body`, `text-caption` classes throughout.
- Update the report viewer card styling to use `--card` background.

- [ ] **Step 3: Restyle InsightsPage**

Update `frontend/src/pages/InsightsPage.tsx`:
- Replace badge-based strength indicators with `insight-card` class + strength modifier.
- Group cards under `text-title` section headers ("Established" and "Collecting Data").
- Apply typography classes.

- [ ] **Step 4: Restyle BloodworkPage**

Update `frontend/src/pages/BloodworkPage.tsx`:
- Replace the inline expanding add-panel form with a "Add Panel" button that opens a `<BottomSheet>`.
- Move the form content (date picker, lab name, marker dropdown, value inputs, + Row button, save) into the sheet.
- Apply new card and typography styles throughout.
- Update chart tooltip styling to use `--card-elevated`.

- [ ] **Step 5: Reorganize SettingsPage**

Update `frontend/src/pages/SettingsPage.tsx` sections:
1. **Profile section** (existing targets card — restyled)
2. **Dashboard section** — new card with a link/button "Customize Dashboard Metrics" that opens the same customization sheet as the dashboard long-press. For now, render the toggle list inline: list each metric from `METRIC_DEFS` with an on/off toggle and drag handle.
3. **Integrations section** — existing MFP card + Garmin status badge (restyled)
4. **Data section** — sync button + sync history table (restyled)
5. **About section** — app version string

Apply `text-title` for section headers, `--card` for card backgrounds, consistent 16px padding.

- [ ] **Step 6: Restyle FoodLogPage and FoodDetailPage**

Update both pages:
- Apply new color palette and typography classes.
- Replace X/delete buttons with `SwipeToDelete` where applicable.
- Use Lucide icons (`Search`, `Camera`, `ScanLine`, `Plus`, `Star`, `ArrowLeft`).
- Update all card backgrounds to `--card`, borders to `--border`.
- Ensure the barcode/label scanner cards use `--card-elevated` for modal feel.

- [ ] **Step 7: Verify build**

```bash
cd frontend && npm run build
```

Expected: Build succeeds. All secondary pages render with consistent new styling.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat: restyle settings, AI, bloodwork, insights, food pages"
```

---

### Task 9: PWA Notifications

**Files:**
- Create: `frontend/src/notifications.ts` — notification permission, scheduling, and management
- Modify: `frontend/src/pages/SettingsPage.tsx` — add notifications section with per-type toggles
- Modify: `frontend/public/sw.js` or `vite.config.ts` PWA config — register notification handlers

**Interfaces:**
- Consumes: Existing service worker from vite-plugin-pwa. localStorage for notification preferences.
- Produces: `requestNotificationPermission()`, `scheduleNotification(type, config)`, `cancelNotification(type)` functions. Settings UI with per-type toggles.

- [ ] **Step 1: Create notification manager**

Create `frontend/src/notifications.ts`:

```ts
export type NotificationType = 'checkin' | 'workout' | 'streak' | 'sync_stale' | 'goal_nudge'

interface NotificationConfig {
  enabled: boolean
  time?: string // HH:MM
  days?: number[] // 0=Sun, 1=Mon, etc.
}

const STORAGE_KEY = 'notification-config'

const DEFAULTS: Record<NotificationType, NotificationConfig> = {
  checkin: { enabled: false, time: '21:00' },
  workout: { enabled: false, time: '07:00', days: [1, 3, 5] },
  streak: { enabled: false, time: '20:00' },
  sync_stale: { enabled: false },
  goal_nudge: { enabled: false, time: '18:00' },
}

export function getNotificationConfig(): Record<NotificationType, NotificationConfig> {
  const saved = localStorage.getItem(STORAGE_KEY)
  if (saved) {
    const parsed = JSON.parse(saved)
    return { ...DEFAULTS, ...parsed }
  }
  return { ...DEFAULTS }
}

export function saveNotificationConfig(config: Record<NotificationType, NotificationConfig>) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(config))
  // Re-register with service worker
  registerNotifications(config)
}

export async function requestNotificationPermission(): Promise<boolean> {
  if (!('Notification' in window)) return false
  if (Notification.permission === 'granted') return true
  const result = await Notification.requestPermission()
  return result === 'granted'
}

export function registerNotifications(config: Record<NotificationType, NotificationConfig>) {
  // For PWA on iOS, we use a simplified approach:
  // Schedule local notifications via the service worker's periodic sync
  // or use setTimeout-based scheduling when the app is open.
  // Full push notifications require a backend push server — for v1,
  // we use in-app reminders when the PWA is open.

  if (!('serviceWorker' in navigator)) return

  navigator.serviceWorker.ready.then(reg => {
    // Post notification config to service worker
    reg.active?.postMessage({
      type: 'NOTIFICATION_CONFIG',
      config,
    })
  })
}

export const NOTIFICATION_LABELS: Record<NotificationType, { label: string, description: string }> = {
  checkin: { label: 'Evening check-in', description: 'Remind me to log my day' },
  workout: { label: 'Workout reminder', description: 'Scheduled training days' },
  streak: { label: 'Streak maintenance', description: "Don't break your streak" },
  sync_stale: { label: 'Sync alerts', description: 'Garmin data is outdated' },
  goal_nudge: { label: 'Goal nudges', description: 'Protein/step targets' },
}
```

- [ ] **Step 2: Add notifications section to SettingsPage**

Add to the Settings page after the Dashboard section:

```tsx
import {
  getNotificationConfig, saveNotificationConfig,
  requestNotificationPermission, NOTIFICATION_LABELS,
  type NotificationType,
} from '../notifications'

// Inside the component:
const [notifConfig, setNotifConfig] = useState(getNotificationConfig)

async function toggleNotification(type: NotificationType) {
  const current = notifConfig[type]
  if (!current.enabled) {
    const granted = await requestNotificationPermission()
    if (!granted) return
  }
  const updated = {
    ...notifConfig,
    [type]: { ...current, enabled: !current.enabled },
  }
  setNotifConfig(updated)
  saveNotificationConfig(updated)
}

function setNotifTime(type: NotificationType, time: string) {
  const updated = {
    ...notifConfig,
    [type]: { ...notifConfig[type], time },
  }
  setNotifConfig(updated)
  saveNotificationConfig(updated)
}

// In the JSX, render a Notifications card:
<div className="card">
  <div className="text-title" style={{ marginBottom: 12 }}>Notifications</div>
  {(Object.keys(NOTIFICATION_LABELS) as NotificationType[]).map(type => {
    const { label, description } = NOTIFICATION_LABELS[type]
    const config = notifConfig[type]
    return (
      <div key={type} style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '12px 0', borderBottom: '1px solid var(--border)',
      }}>
        <div>
          <div className="text-body">{label}</div>
          <div className="text-caption">{description}</div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {config.enabled && config.time !== undefined && (
            <input
              type="time"
              value={config.time}
              onChange={e => setNotifTime(type, e.target.value)}
              style={{
                background: 'var(--card-elevated)', border: '1px solid var(--border)',
                borderRadius: 8, color: 'var(--text)', padding: '4px 8px', fontSize: '0.8rem',
              }}
            />
          )}
          <button
            onClick={() => toggleNotification(type)}
            style={{
              width: 48, height: 28, borderRadius: 14, border: 'none',
              background: config.enabled ? 'var(--accent)' : 'var(--border)',
              position: 'relative', transition: 'background 0.2s',
            }}
          >
            <div style={{
              width: 22, height: 22, borderRadius: '50%', background: 'white',
              position: 'absolute', top: 3,
              left: config.enabled ? 23 : 3,
              transition: 'left 0.2s',
            }} />
          </button>
        </div>
      </div>
    )
  })}
</div>
```

- [ ] **Step 3: Verify build**

```bash
cd frontend && npm run build
```

Expected: Build succeeds. Notifications section appears in Settings with toggles and time pickers.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat: add PWA notification system with configurable alerts"
```

---

### Task 10: Final Cleanup & Polish

**Files:**
- Modify: `frontend/src/index.css` — remove orphaned styles from deleted pages, ensure consistency
- Modify: `frontend/src/App.tsx` — verify all routes, remove dead imports
- Remove any orphaned component imports throughout

**Interfaces:**
- Consumes: All components from Tasks 1-9.
- Produces: Clean, build-passing frontend with no dead code.

- [ ] **Step 1: Remove orphaned CSS**

In `frontend/src/index.css`, remove CSS rules that were only used by deleted pages:
- `.sync-btn` (replaced by header button)
- Any MorePage-specific styles
- Old `.nav .icon` emoji-specific styles

Keep all styles that are still referenced by existing components. When unsure, grep the `src/` directory for the class name.

- [ ] **Step 2: Verify no dead imports**

Run the linter to catch unused imports:

```bash
cd frontend && npm run lint
```

Fix any unused import warnings by removing the imports.

- [ ] **Step 3: Verify full build**

```bash
cd frontend && npm run build
```

Expected: Build succeeds with no warnings about missing modules.

- [ ] **Step 4: Manual smoke test checklist**

Open the app on iPhone (or Chrome DevTools mobile emulation):
- [ ] Home tab loads with metrics row, activities, log summary, trends, insights
- [ ] Tapping a metric card opens drill-down with charts
- [ ] Log tab shows date nav, streak, check-in card, nutrition, meal cards
- [ ] Check-in opens as bottom sheet, saves correctly
- [ ] Quick actions (weight, note) open as bottom sheets
- [ ] Workouts tab shows history, strength, cardio sub-tabs
- [ ] Starting a workout: no sync button overlap, search works full-screen
- [ ] Sets are tap-to-edit and swipe-to-delete
- [ ] Rest timer allows custom seconds
- [ ] Settings shows all sections including notifications
- [ ] AI page has proper chat bubbles and reports
- [ ] All navigation transitions work (horizontal tab switch, vertical drill-down)
- [ ] Safe area insets respected on notched devices
- [ ] No visual overflow on any screen
- [ ] Skeleton loaders appear during data fetch

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "chore: cleanup orphaned styles and dead imports after UI revamp"
```

---

## Implementation Notes

**Risk areas:**
1. The `Dashboard.tsx` rewrite is the largest single change. If the existing API response shape doesn't match the field names used in `getMetricValue()`, adjust the field mapping.
2. The check-in bottom sheet port from `CheckinPage.tsx` requires moving all form state and mutations. The executing agent must fully port this — not leave placeholders.
3. `SwipeToDelete` touch handling may need tuning on iOS Safari. Test threshold sensitivity on a real device.
4. The exercise picker full-screen approach changes from a bottom sheet to a fixed overlay — verify keyboard behavior on iOS Safari specifically.

**What's NOT changing:**
- Backend API — zero changes
- React Query patterns — same queryKey conventions
- API client (`client.ts`) — unchanged
- API types (`types.ts`) — one addition (`MetricConfig`), rest unchanged
- Build pipeline, Vite config, PWA config — unchanged except notification service worker additions
