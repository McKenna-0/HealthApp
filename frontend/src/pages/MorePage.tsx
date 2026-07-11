import { Link } from 'react-router-dom'

const links = [
  { to: '/sleep', icon: '😴', label: 'Sleep', desc: 'Stages, score, overnight HRV' },
  { to: '/weight', icon: '⚖️', label: 'Weight & Energy', desc: 'Trend, TDEE, energy balance' },
  { to: '/bloodwork', icon: '🩸', label: 'Bloodwork', desc: 'Lab panels & marker history' },
  { to: '/settings', icon: '⚙️', label: 'Settings', desc: 'Targets, sync, data source' },
]

export default function MorePage() {
  return (
    <>
      <h1>More</h1>
      {links.map((l) => (
        <Link key={l.to} to={l.to} style={{ textDecoration: 'none', color: 'inherit' }}>
          <div className="card row" style={{ alignItems: 'center' }}>
            <span className="fixed" style={{ fontSize: '1.6rem' }}>
              {l.icon}
            </span>
            <div>
              <div>{l.label}</div>
              <div className="muted">{l.desc}</div>
            </div>
          </div>
        </Link>
      ))}
    </>
  )
}
