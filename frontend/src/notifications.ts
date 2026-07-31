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
    try {
      const parsed = JSON.parse(saved)
      return { ...DEFAULTS, ...parsed }
    } catch {
      // fall through to defaults
    }
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

export const NOTIFICATION_LABELS: Record<NotificationType, { label: string; description: string }> = {
  checkin: { label: 'Evening check-in', description: 'Remind me to log my day' },
  workout: { label: 'Workout reminder', description: 'Scheduled training days' },
  streak: { label: 'Streak maintenance', description: "Don't break your streak" },
  sync_stale: { label: 'Sync alerts', description: 'Garmin data is outdated' },
  goal_nudge: { label: 'Goal nudges', description: 'Protein/step targets' },
}
