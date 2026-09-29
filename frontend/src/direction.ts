export const DIRECTION_OPTIONS = [
  { value: 'up', label: '上行' },
  { value: 'down', label: '下行' },
] as const

export function directionLabel(d: string | null | undefined): string {
  if (d === 'down') return '下行'
  if (d === 'up') return '上行'
  return '上行'
}
