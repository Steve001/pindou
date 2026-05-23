import { defineStore } from 'pinia'
import { fetchPalettes, downloadPDF } from '../api/index.js'

let _debounceTimer = null

const CARD_STORAGE_KEY = 'bead_card'

function loadCardState() {
  try {
    const raw = localStorage.getItem(CARD_STORAGE_KEY)
    if (!raw) return null
    const state = JSON.parse(raw)
    const now = Date.now()
    const expiresAt = state.activatedAt + state.durationDays * 86400000
    if (now >= expiresAt) {
      localStorage.removeItem(CARD_STORAGE_KEY)
      return null
    }
    return state
  } catch {
    return null
  }
}

function saveCardState(code, durationDays) {
  localStorage.setItem(CARD_STORAGE_KEY, JSON.stringify({
    code,
    durationDays,
    activatedAt: Date.now(),
  }))
}

export const useAppStore = defineStore('app', {
  state: () => ({
    palettes: [],
    selectedPaletteId: 'default',

    gridWidth: 48,
    gridHeight: 0,
    lockAspectRatio: true,

    brightness: 1.0,
    contrast: 1.0,
    saturation: 1.0,

    dithering: true,
    flipH: false,
    flipV: false,
    showGrid: true,
    transparentBg: false,
    pixelate: false,

    mergeValue: 0,
    showCoords: true,
    highlightIndex: -1,
    replaceColors: {},

    uploadedFile: null,
    uploadedPreviewUrl: null,

    generating: false,
    result: null,
    locked: true,

    cardCode: '',
    cardUnlocked: false,

    excludedColors: [],

    error: null,
  }),

  getters: {
    paletteName: (state) => {
      const p = state.palettes.find((p) => p.id === state.selectedPaletteId)
      return p ? p.name : ''
    },
    maxGridSize: (state) => {
      return state.cardUnlocked ? 300 : 50
    },
    canGenerate: (state) => {
      return state.uploadedFile && !state.generating
    },
  },

  actions: {
    async loadPalettes() {
      try {
        this.palettes = await fetchPalettes()
      } catch (e) {
        this.error = e.message
      }
    },

    _buildFormData() {
      const fd = new FormData()
      fd.append('image', this.uploadedFile)
      fd.append('grid_width', this.gridWidth)
      fd.append('grid_height', this.gridHeight)
      fd.append('palette_id', this.selectedPaletteId)
      fd.append('brightness', this.brightness)
      fd.append('contrast', this.contrast)
      fd.append('saturation', this.saturation)
      fd.append('dithering', this.dithering ? 'true' : 'false')
      fd.append('flip_h', this.flipH ? 'true' : 'false')
      fd.append('flip_v', this.flipV ? 'true' : 'false')
      fd.append('show_grid', this.showGrid ? 'true' : 'false')
      fd.append('transparent_bg', this.transparentBg ? 'true' : 'false')
      fd.append('pixelate', this.pixelate ? 'true' : 'false')
      fd.append('merge_value', this.mergeValue)
      fd.append('show_coords', this.showCoords ? 'true' : 'false')
      fd.append('highlight_index', this.highlightIndex)
      if (Object.keys(this.replaceColors).length > 0) {
        fd.append('replace_colors', JSON.stringify(this.replaceColors))
      }
      if (this.excludedColors.length > 0) {
        fd.append('exclude_colors', JSON.stringify(this.excludedColors))
      }
      return fd
    },

    async generate() {
      if (!this.uploadedFile) return
      this.generating = true
      this.error = null

      try {
        const fd = this._buildFormData()
        const endpoint = this.cardUnlocked ? '/api/regenerate' : '/api/generate'
        if (this.cardUnlocked) {
          fd.append('card_code', this.cardCode.trim())
        }

        const res = await fetch(endpoint, { method: 'POST', body: fd })
        const data = await res.json()
        if (!res.ok) throw new Error(data.detail || '生成失败')
        this.result = data
        this.locked = !this.cardUnlocked
      } catch (e) {
        this.error = e.message
      } finally {
        this.generating = false
      }
    },

    scheduleGenerate() {
      if (!this.uploadedFile) return
      clearTimeout(_debounceTimer)
      _debounceTimer = setTimeout(() => this.generate(), 500)
    },

    excludeColor(idx) {
      if (!this.excludedColors.includes(idx)) {
        this.excludedColors.push(idx)
        this.scheduleGenerate()
      }
    },

    resetExcludedColors() {
      this.excludedColors = []
      if (this.result) this.scheduleGenerate()
    },

    setHighlight(idx) {
      if (this.highlightIndex === idx) {
        this.highlightIndex = -1
      } else {
        this.highlightIndex = idx
      }
      this.scheduleGenerate()
    },

    clearHighlight() {
      this.highlightIndex = -1
      if (this.result) this.scheduleGenerate()
    },

    resetReplaceColors() {
      this.replaceColors = {}
      if (this.result) this.scheduleGenerate()
    },

    checkCardState() {
      const state = loadCardState()
      if (state) {
        this.cardCode = state.code
        this.cardUnlocked = true
        this.locked = false
      }
    },

    async unlockCard() {
      if (!this.cardCode.trim()) return
      this.error = null
      try {
        const res = await fetch('/api/unlock', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ card_code: this.cardCode.trim() }),
        })
        const data = await res.json()
        if (data.valid) {
          saveCardState(this.cardCode.trim(), data.duration_days)
          this.cardUnlocked = true
          this.locked = false
          if (this.result) {
            await this.generate()
          }
        } else {
          this.error = data.message
        }
      } catch (e) {
        this.error = e.message
      }
    },

    async exportPDF() {
      if (!this.result || !this.cardUnlocked) return
      try {
        const blob = await downloadPDF({
          imageBase64: this.result.image_base64,
          gridWidth: this.result.grid_width,
          gridHeight: this.result.grid_height,
          colorsUsed: this.result.colors_used,
          paletteName: this.paletteName,
          cardCode: this.cardCode.trim(),
        })
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `bead-pattern-${Date.now()}.pdf`
        a.click()
        URL.revokeObjectURL(url)
      } catch (e) {
        this.error = e.message
      }
    },

    setFile(file) {
      this.uploadedFile = file
      this.excludedColors = []
      this.highlightIndex = -1
      this.replaceColors = {}
      if (file) {
        const reader = new FileReader()
        reader.onload = (e) => {
          this.uploadedPreviewUrl = e.target.result
        }
        reader.readAsDataURL(file)
      } else {
        this.uploadedPreviewUrl = null
      }
    },

    async removeBg() {
      if (!this.uploadedFile) return
      this.error = null
      try {
        const fd = new FormData()
        fd.append('image', this.uploadedFile)
        const res = await fetch('/api/remove-bg', { method: 'POST', body: fd })
        const data = await res.json()
        if (!res.ok) throw new Error(data.detail || '抠图失败')

        // Convert base64 back to File
        const byteChars = atob(data.image_base64)
        const byteArray = new Uint8Array(byteChars.length)
        for (let i = 0; i < byteChars.length; i++) {
          byteArray[i] = byteChars.charCodeAt(i)
        }
        const blob = new Blob([byteArray], { type: 'image/png' })
        const file = new File([blob], 'removed-bg.png', { type: 'image/png' })
        this.setFile(file)
      } catch (e) {
        this.error = e.message
      }
    },

    clearError() {
      this.error = null
    },
  },
})
