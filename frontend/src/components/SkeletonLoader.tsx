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
