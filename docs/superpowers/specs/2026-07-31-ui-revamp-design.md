# UI Revamp — Full Redesign Spec

**Date**: 2026-07-31
**Approach**: Full redesign (Approach B) — Clean minimal aesthetic (Oura/Whoop-inspired)

## 1. Navigation & App Shell

### 3-Tab Bottom Nav
- **Home** | **Log** | **Workouts**
- Lucide icons with labels. Active = accent fill, inactive = muted stroke.
- Settings via gear icon in header (top-right).
- AI page via sparkle icon in header (left of gear).
- Sync button in header bar, left of AI/gear icons. Hidden during active workout.

### Header Bar
- Page title left-aligned, action icons right-aligned.
- Subtle bottom border, no background color.
- During active workout: shows workout timer + "Finish" button instead of sync.

### Transitions
- Horizontal slide for tab switches.
- Vertical slide-up for drill-downs, modals, bottom sheets.

### Safe Areas
- `env(safe-area-inset-top)` and `env(safe-area-inset-bottom)` respected throughout.
- Bottom nav sits above home indicator.

---

## 2. Design System

### Typography (rem-based)
| Level   | Size     | Weight   | Usage                              |
|---------|----------|----------|------------------------------------|
| Display | 1.75rem  | 700      | Page titles, primary metric values |
| Title   | 1.15rem  | 600      | Card headers, section titles       |
| Body    | 0.9rem   | 400      | Content text, list items           |
| Caption | 0.75rem  | 400      | Labels, timestamps, secondary info |

### Spacing Tokens (4px base)
`4, 8, 12, 16, 24, 32` — used for all gaps, padding, margins.

### Color Palette
| Token         | Value     | Usage                           |
|---------------|-----------|----------------------------------|
| --bg          | #0B1120   | App background                  |
| --card        | #151E2F   | Card surface                    |
| --card-elevated | #1C2740 | Modals, sheets, active states   |
| --border      | #243044   | Card borders, dividers          |
| --text        | #E8ECF1   | Primary text                    |
| --muted       | #7A8BA5   | Secondary text, labels          |
| --accent      | #3B9EFF   | Primary actions, active states  |
| --green       | #34D399   | Success, positive deltas        |
| --red         | #F87171   | Error, negative deltas, delete  |
| --amber       | #FBBF24   | Warning, partial states         |

### Icons
- Lucide React throughout. 20px in UI, 24px in nav.
- Emojis only for mood selector.

### Cards
- 16px padding, 14px border-radius, 1px solid `--border`.
- No shadows. 12px gap between stacked cards.

### Interactive States
- Minimum 44px tap targets.
- Pressed: opacity 0.7 briefly.
- Skeleton loaders (pulse animation) replace all "Loading..." text.

---

## 3. Home Dashboard

### Layout (top to bottom)

1. **Header**: "Today" (or date) with nav arrows. AI sparkle + gear icons right.

2. **Metrics Row** (horizontally scrollable, customizable):
   - Compact cards: Lucide icon + label, current value (large), delta vs 7d avg (color-coded).
   - Default set: HRV, Sleep Score, Calories Burned, Steps, Resting HR, Body Battery.
   - Tap → metric drill-down view.
   - Long-press or edit button → customization sheet (toggle on/off, drag to reorder).
   - Customization stored in localStorage (no backend change needed). Key: `dashboard-metrics-config`.

3. **Recent Activities**: Last 3 workouts as compact cards (type icon, name, duration, key stat). "See all" → Workouts tab.

4. **Today's Log Summary**: Calories progress ring, macro bars, mood, alcohol/caffeine, eating window. Tap → Log tab. CTA "Check in" button if not completed.

5. **Trends Section** (collapsible): Small sparkline charts for pinned metrics. Tap → drill-down.

6. **AI Insights**: Top 1-2 established correlations as compact cards. Tap → Insights page.

7. **Readiness Card**: Color-coded status with expandable component breakdown (if data available).

---

## 4. Metric Drill-Down Views

Slide-up view triggered by tapping any metric card.

### Consistent Layout
1. **Header**: Back arrow + metric name + current value (display size).
2. **Summary row**: Today, 7d avg, 30d avg, trend direction.
3. **Primary chart**: Full-width, range picker (7/30/90/1Y), touch-to-inspect.
4. **AI insight snippet**: Contextual observation card, cached or generated on-demand.
5. **Metric-specific breakdown**:
   - Sleep: stages stacked bar, overnight HRV, bedtime consistency
   - HRV: morning vs evening, day-of-week pattern
   - Weight: trend line, TDEE, goal ETA, energy balance
   - Calories burned: activity vs resting, by workout type
   - Steps: hourly distribution, daily goal progress
   - Resting HR: trend with exercise load overlay
6. **History table**: Last 14 entries, date + value + delta.

### Pages Absorbed
- SleepPage → Sleep drill-down
- WeightEnergyPage → Weight drill-down
- These standalone pages are removed.

---

## 5. Log Tab

### Layout (top to bottom)

1. **Date bar**: Left/right arrows + "Today" (tappable date picker). Streak row underneath (restyled dots, flame icon).

2. **Daily Check-in Card**:
   - Not completed: "How's your day?" CTA with mood emoji row, "Full check-in" button.
   - Completed: compact summary (mood, alcohol, caffeine, illness, eating window, note). Tap to edit.
   - Check-in opens as a **bottom sheet**, not a page navigation.
   - Check-in sheet includes: mood (5 emojis), alcohol stepper, caffeine stepper + time, illness toggle, weight input, eating window times, note textarea.

3. **Nutrition Summary Card**:
   - Calorie donut + progress toward target.
   - Macro bars (protein/carbs/fat with grams).
   - Source badge ("via MFP" or manual count).
   - Tap → expands to meal breakdown list.
   - Individual food items visible when expanded, swipe-left-to-delete.

4. **Quick Actions Row**: Horizontal pill buttons:
   - "Sync MFP" (if connected)
   - "Quick add food" (name + kcal bottom sheet)
   - "Log weight" (bottom sheet)
   - "Add note" (bottom sheet)

5. **Activity Summary**: Today's workouts as compact cards (if any).

6. **Copy Yesterday**: Subtle text button at bottom.

---

## 6. Workouts Tab

### Sub-tabs (chips): History | Strength | Cardio

**History tab**:
- "Start Workout" full-width accent button at top.
- Active session pulsing banner (if in progress).
- Workout list: cards with Lucide icon, name, date, duration, key stat. Swipe-left-to-delete.
- "Routines" button next to start button.

**Strength tab**: Muscle body map + weekly volume/sets charts + exercise progression (restyled).

**Cardio tab**: Type selector + distance/pace/load charts (restyled).

### Active Workout UX Fixes

1. **Sync button hidden** during workout. Header shows timer + "Finish".
2. **Exercise search**: Full-screen sheet, search input fixed top, results scroll between search bar and keyboard.
3. **Tap-to-edit sets**: Tapping a logged set expands it inline with editable weight/reps/RPE. Tap "Save" or tap away to confirm.
4. **Swipe-to-delete**: Sets and exercises use swipe-left pattern. No X buttons.
5. **Custom rest timer**: Number input alongside presets (60/90/120/180). Arbitrary seconds. Optional per-exercise timer.
6. **Exercise stats mid-workout**: Tap exercise name → compact stats sheet (last 3 sessions, PR, mini progression chart).
7. **Font optimization**: Typography scale applied. Long names truncate. Inputs sized for 4 digits.

---

## 7. Swipe-to-Delete (App-Wide)

### Pattern
- Swipe left reveals red area with trash icon.
- Past 50% threshold: auto-triggers delete with height collapse animation (200ms ease).
- Short swipe + tap trash also works.
- Haptic feedback on threshold cross (via `navigator.vibrate`).

### Applied To
- Food log entries
- Workout sets and exercises
- Weight history entries
- Context log entries
- Sync history rows
- Workout history cards

### Confirmation
- Only for high-value destructive actions: delete entire workout, disconnect MFP.
- Individual items delete instantly, no confirm dialog.

---

## 8. Notifications (PWA Web Push)

### Available Types
| Type                  | Default Time | Default State |
|-----------------------|-------------|---------------|
| Evening check-in      | 21:00       | Off           |
| Workout reminder      | 07:00 (configurable days) | Off |
| Streak maintenance    | 20:00       | Off           |
| Data sync stale       | (12h threshold) | Off        |
| Goal nudges           | 18:00       | Off           |

### Implementation
- Web Push API + service worker.
- Each type: on/off toggle + time/day configuration in Settings.
- All off by default. One-time opt-in prompt on first home page visit.
- Goal nudges require MFP sync or manual food logging for calorie/macro data.

---

## 9. Settings Page

Accessed via gear icon in header. Organized into sections:

1. **Profile**: Calorie target, weight goal, macro targets (grams vs % toggle).
2. **Dashboard**: Customize metrics — toggle and reorder. Shared state with dashboard long-press.
3. **Notifications**: Toggle each type, set times/days per type.
4. **Integrations**: Garmin status/badge, MFP sync card (cookie input, status, sync/disconnect).
5. **Data**: Manual sync button, sync history table, data source info.
6. **About**: App version, future: data export.

---

## 10. Bloodwork, Insights, AI

### Bloodwork
- Accessed from Settings → "Health Records" section, or pinned dashboard metric.
- Functionally identical, restyled. Panel entry via bottom sheet.

### Insights
- Accessed via AI insight cards on dashboard or AI page.
- Restyled: strength-colored left border on cards (strong=red, moderate=amber, weak=blue).
- Grouped: "Established" vs "Collecting data."

### AI Page (header sparkle icon)
- Two tabs: Reports | Chat.
- Reports: generate, history list, markdown viewer (restyled).
- Chat: proper chat bubble UI (user=right/accent, AI=left/card). Fixed input bar at bottom.
- Context-aware: opened from drill-down "Ask about this" pre-fills relevant context.

---

## 11. Pages Removed
- **MorePage**: eliminated. All links absorbed into dashboard drill-downs or settings.
- **SleepPage**: absorbed into sleep metric drill-down.
- **WeightEnergyPage**: absorbed into weight metric drill-down.
- **OtherLogsPage**: weight logging → Log tab quick action sheet. Context logging → check-in sheet.

## 12. Pages Kept (Restyled)
- **FoodDetailPage**: slide-up from meal expansion.
- **FoodLogPage**: slide-up from nutrition card interaction.
- **WorkoutDetailPage**: slide-up from workout cards.
- **WorkoutSummaryPage**: slide-up from workout detail.
- **ExerciseStatsPage**: slide-up from exercise name tap.
- **RoutinesPage**: slide-up from workouts tab.
- **CheckinPage**: converted to bottom sheet (no longer standalone page).
- **BloodworkPage**: restyled, accessed from settings.
- **InsightsPage**: restyled, accessed from dashboard/AI.
