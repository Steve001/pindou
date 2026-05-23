const API_BASE = '/api'

export async function fetchPalettes() {
  const res = await fetch(`${API_BASE}/palettes`)
  if (!res.ok) throw new Error('获取色板列表失败')
  return res.json()
}

export async function fetchPaletteDetail(paletteId) {
  const res = await fetch(`${API_BASE}/palettes/${paletteId}`)
  if (!res.ok) throw new Error('获取色板详情失败')
  return res.json()
}

export async function downloadPDF({ imageBase64, gridWidth, gridHeight, colorsUsed, paletteName, cardCode }) {
  const res = await fetch(`${API_BASE}/export-pdf`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      image_base64: imageBase64,
      grid_width: gridWidth,
      grid_height: gridHeight,
      colors_used: colorsUsed,
      palette_name: paletteName,
      card_code: cardCode,
    }),
  })
  if (!res.ok) throw new Error('PDF导出需要有效卡密')
  return res.blob()
}
