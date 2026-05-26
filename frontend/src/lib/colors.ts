const palette = [
  '#38bdf8',
  '#22c55e',
  '#f97316',
  '#a855f7',
  '#facc15',
  '#06b6d4',
  '#f43f5e',
  '#84cc16',
]

export const colorFromId = (id: string) => {
  const hash = Array.from(id).reduce((acc, char) => acc + char.charCodeAt(0), 0)
  return palette[hash % palette.length]
}
