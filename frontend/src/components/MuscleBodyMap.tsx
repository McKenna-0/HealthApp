// Stylized front/back body heatmap. Deliberately schematic (not anatomical):
// muscle regions are simple shapes positioned over a neutral silhouette,
// tinted from slate to red by work intensity (0..1).

interface Shape {
  muscle: string
  kind: 'ellipse' | 'rect'
  cx: number
  cy: number
  rx: number
  ry: number
  rotate?: number
}

function m(
  muscle: string,
  cx: number,
  cy: number,
  rx: number,
  ry: number,
  rotate = 0,
  kind: 'ellipse' | 'rect' = 'ellipse',
): Shape {
  return { muscle, kind, cx, cy, rx, ry, rotate }
}

const FRONT: Shape[] = [
  m('traps', 80, 57, 13, 6, -12),
  m('traps', 120, 57, 13, 6, 12),
  m('front_delts', 64, 77, 9, 12),
  m('front_delts', 136, 77, 9, 12),
  m('side_delts', 50, 84, 6, 11, -8),
  m('side_delts', 150, 84, 6, 11, 8),
  m('chest', 82, 97, 16, 13),
  m('chest', 118, 97, 16, 13),
  m('biceps', 51, 122, 8, 15, 10),
  m('biceps', 149, 122, 8, 15, -10),
  m('forearms', 41, 168, 6, 19, 8),
  m('forearms', 159, 168, 6, 19, -8),
  m('abs', 100, 147, 14, 30, 0, 'rect'),
  m('obliques', 78, 142, 6, 21),
  m('obliques', 122, 142, 6, 21),
  m('quads', 84, 246, 12, 37),
  m('quads', 116, 246, 12, 37),
  m('calves', 82, 328, 8, 22),
  m('calves', 118, 328, 8, 22),
]

const BACK: Shape[] = [
  m('traps', 100, 68, 22, 15),
  m('rear_delts', 58, 80, 9, 11),
  m('rear_delts', 142, 80, 9, 11),
  m('upper_back', 100, 100, 19, 16, 0, 'rect'),
  m('lats', 76, 128, 12, 25, 12),
  m('lats', 124, 128, 12, 25, -12),
  m('lower_back', 100, 165, 12, 15, 0, 'rect'),
  m('triceps', 50, 122, 8, 15, 10),
  m('triceps', 150, 122, 8, 15, -10),
  m('forearms', 41, 168, 6, 19, 8),
  m('forearms', 159, 168, 6, 19, -8),
  m('glutes', 86, 202, 13, 14),
  m('glutes', 114, 202, 13, 14),
  m('hamstrings', 84, 258, 11, 33),
  m('hamstrings', 116, 258, 11, 33),
  m('calves', 82, 328, 9, 23),
  m('calves', 118, 328, 9, 23),
]

const BASE = { r: 0x33, g: 0x41, b: 0x55 } // --border slate
const HOT = { r: 0xef, g: 0x44, b: 0x44 } // red-500

function heat(intensity: number): string {
  const t = Math.max(0, Math.min(1, intensity))
  const r = Math.round(BASE.r + (HOT.r - BASE.r) * t)
  const g = Math.round(BASE.g + (HOT.g - BASE.g) * t)
  const b = Math.round(BASE.b + (HOT.b - BASE.b) * t)
  return `rgb(${r},${g},${b})`
}

function Silhouette() {
  const s = { fill: '#1e293b', stroke: '#334155', strokeWidth: 1.5 }
  return (
    <g>
      <circle cx={100} cy={28} r={16} {...s} />
      <rect x={92} y={42} width={16} height={14} rx={5} {...s} />
      {/* torso */}
      <path
        d="M 56 62 Q 100 52 144 62 L 138 130 Q 132 180 126 196 L 74 196 Q 68 180 62 130 Z"
        {...s}
      />
      {/* arms */}
      <path d="M 56 64 Q 40 90 44 140 L 36 200 Q 34 212 42 212 Q 50 212 51 200 L 60 142 L 66 92 Z" {...s} />
      <path d="M 144 64 Q 160 90 156 140 L 164 200 Q 166 212 158 212 Q 150 212 149 200 L 140 142 L 134 92 Z" {...s} />
      {/* legs */}
      <path d="M 74 196 L 70 290 L 74 368 Q 75 376 83 376 Q 90 376 90 368 L 94 288 L 97 210 Z" {...s} />
      <path d="M 126 196 L 130 290 L 126 368 Q 125 376 117 376 Q 110 376 110 368 L 106 288 L 103 210 Z" {...s} />
    </g>
  )
}

function View({
  shapes,
  intensities,
  label,
}: {
  shapes: Shape[]
  intensities: Record<string, number>
  label: string
}) {
  return (
    <svg viewBox="0 0 200 400" className="body-map-view" role="img" aria-label={`${label} muscle map`}>
      <Silhouette />
      {shapes.map((sh, i) => {
        const v = intensities[sh.muscle] ?? 0
        const fill = heat(v)
        const opacity = v > 0 ? 0.95 : 0.55
        if (sh.kind === 'rect') {
          return (
            <rect
              key={i}
              x={sh.cx - sh.rx}
              y={sh.cy - sh.ry}
              width={sh.rx * 2}
              height={sh.ry * 2}
              rx={Math.min(sh.rx, 10)}
              fill={fill}
              opacity={opacity}
              transform={sh.rotate ? `rotate(${sh.rotate} ${sh.cx} ${sh.cy})` : undefined}
            />
          )
        }
        return (
          <ellipse
            key={i}
            cx={sh.cx}
            cy={sh.cy}
            rx={sh.rx}
            ry={sh.ry}
            fill={fill}
            opacity={opacity}
            transform={sh.rotate ? `rotate(${sh.rotate} ${sh.cx} ${sh.cy})` : undefined}
          />
        )
      })}
      <text x={100} y={396} textAnchor="middle" fontSize={13} fill="#64748b">
        {label}
      </text>
    </svg>
  )
}

export default function MuscleBodyMap({
  intensities,
  height = 260,
}: {
  intensities: Record<string, number>
  height?: number
}) {
  return (
    <div className="body-map" style={{ height }}>
      <View shapes={FRONT} intensities={intensities} label="Front" />
      <View shapes={BACK} intensities={intensities} label="Back" />
    </div>
  )
}
