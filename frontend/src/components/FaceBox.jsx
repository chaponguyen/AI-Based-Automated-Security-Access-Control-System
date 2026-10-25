// Agent 3 — Vẽ khung mặt và 5 landmark
function getGeometry(box) {
  if (Array.isArray(box)) {
    return { bounds: box.slice(0, 4), landmarks: box.landmarks || box.kps || [] }
  }
  if (!box || typeof box !== 'object') return null

  const rawBounds = box.bbox || box.box || box.xyxy || box.rect || (
    ['x1', 'y1', 'x2', 'y2'].every((key) => Number.isFinite(Number(box[key])))
      ? [box.x1, box.y1, box.x2, box.y2]
      : Number.isFinite(Number(box.x)) && Number.isFinite(Number(box.y)) &&
        Number.isFinite(Number(box.width)) && Number.isFinite(Number(box.height))
        ? [box.x, box.y, Number(box.x) + Number(box.width), Number(box.y) + Number(box.height)]
        : null
  )
  const bounds = Array.isArray(rawBounds)
    ? rawBounds
    : rawBounds && typeof rawBounds === 'object'
      ? ['x1', 'y1', 'x2', 'y2'].every((key) => Number.isFinite(Number(rawBounds[key])))
        ? [rawBounds.x1, rawBounds.y1, rawBounds.x2, rawBounds.y2]
        : Number.isFinite(Number(rawBounds.x)) && Number.isFinite(Number(rawBounds.y)) &&
          Number.isFinite(Number(rawBounds.width)) && Number.isFinite(Number(rawBounds.height))
          ? [rawBounds.x, rawBounds.y, Number(rawBounds.x) + Number(rawBounds.width), Number(rawBounds.y) + Number(rawBounds.height)]
          : null
      : rawBounds
  return { bounds, landmarks: box.landmarks || box.kps || box.keypoints || [] }
}

function pointCoordinates(point) {
  if (Array.isArray(point) && point.length >= 2) return [Number(point[0]), Number(point[1])]
  if (point && Number.isFinite(Number(point.x)) && Number.isFinite(Number(point.y))) return [Number(point.x), Number(point.y)]
  return null
}

export default function FaceBox({ box, width = 640, height = 480 }) {
  const geometry = getGeometry(box)
  if (!geometry?.bounds || geometry.bounds.length < 4) return null

  const bounds = geometry.bounds.slice(0, 4).map(Number)
  if (!bounds.every(Number.isFinite)) return null
  const validLandmarks = (Array.isArray(geometry.landmarks) ? geometry.landmarks : [])
    .map(pointCoordinates)
    .filter(Boolean)
    .slice(0, 5)
  const normalized = [...bounds, ...validLandmarks.flat()].every((value) => Math.abs(value) <= 1)
  const viewWidth = normalized ? 1 : width
  const viewHeight = normalized ? 1 : height
  const [x1, y1, x2, y2] = bounds

  return (
    <svg className="face-box-overlay" viewBox={`0 0 ${viewWidth} ${viewHeight}`} preserveAspectRatio="none" aria-label="Khung khuôn mặt và năm điểm landmark">
      <rect className="face-box-overlay__rect" x={x1} y={y1} width={x2 - x1} height={y2 - y1} />
      {validLandmarks.map(([x, y], index) => <circle className="face-box-overlay__point" key={index} cx={x} cy={y} r={normalized ? 0.009 : Math.max(width, height) * 0.009} />)}
    </svg>
  )
}
