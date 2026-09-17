import { Link } from 'react-router-dom'
import {
  TrendingUp, Droplet, FileText, Scale, Target, LayoutGrid,
  Link2, Bell, Settings, ChevronRight,
} from 'lucide-react'
import SyncStatusCard from '../components/SyncStatusCard'

type Row = {
  to: string
  icon: typeof TrendingUp
  color: string
  label: string
  detail?: string
}

/**
 * The hub for everything that is not a daily action.
 *
 * /bloodwork is the reason this page exists: the route and page have always
 * been there, but nothing in the app ever linked to them, so in standalone
 * mode — where there is no URL bar — the page was unreachable.
 */
const SECTIONS: { title: string; rows: Row[] }[] = [
  {
    title: 'Analysis',
    rows: [
      { to: '/insights', icon: TrendingUp, color: 'var(--violet)', label: 'Insights', detail: 'Correlations' },
      { to: '/bloodwork', icon: Droplet, color: 'var(--red)', label: 'Bloodwork', detail: 'Panels' },
      { to: '/ai', icon: FileText, color: 'var(--violet)', label: 'Coach reports' },
    ],
  },
  {
    title: 'Targets',
    rows: [
      { to: '/settings', icon: Scale, color: 'var(--green)', label: 'Weight goal' },
      { to: '/settings', icon: Target, color: 'var(--accent)', label: 'Daily targets' },
      { to: '/settings', icon: LayoutGrid, color: 'var(--accent)', label: 'Tiles on Today' },
    ],
  },
  {
    title: 'App',
    rows: [
      { to: '/settings', icon: Link2, color: 'var(--muted)', label: 'Integrations', detail: 'Garmin, MFP' },
      { to: '/settings', icon: Bell, color: 'var(--muted)', label: 'Notifications' },
      { to: '/settings', icon: Settings, color: 'var(--muted)', label: 'Settings, data & sync history' },
    ],
  },
]

export default function MorePage() {
  return (
    <div style={{ padding: 'var(--s4)' }}>
      <SyncStatusCard />

      {SECTIONS.map((section) => (
        <div key={section.title}>
          <p className="settings-section-header">{section.title}</p>
          <div className="card" style={{ padding: '4px 8px' }}>
            {section.rows.map((row, i) => {
              const Icon = row.icon
              return (
                <Link
                  key={row.label}
                  to={row.to}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 12,
                    minHeight: 48,
                    padding: '0 6px',
                    borderTop: i > 0 ? '1px solid var(--border)' : undefined,
                    textDecoration: 'none',
                    color: 'var(--text)',
                  }}
                >
                  <Icon size={18} color={row.color} style={{ flexShrink: 0 }} />
                  <span style={{ flex: 1, minWidth: 0, fontSize: '0.875rem', fontWeight: 600 }}>
                    {row.label}
                  </span>
                  {row.detail && <span className="text-caption">{row.detail}</span>}
                  <ChevronRight size={16} color="var(--dim)" style={{ flexShrink: 0 }} />
                </Link>
              )
            })}
          </div>
        </div>
      ))}
    </div>
  )
}
