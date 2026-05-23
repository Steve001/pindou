<template>
  <div>
    <div class="stats-summary">
      <div class="stat-box">
        <span class="stat-label">网格大小</span>
        <span class="stat-value">{{ store.result.grid_width }} &times; {{ store.result.grid_height }}</span>
      </div>
      <div class="stat-box">
        <span class="stat-label">使用颜色</span>
        <span class="stat-value">{{ store.result.colors_used.length }}</span>
      </div>
      <div class="stat-box">
        <span class="stat-label">总珠数</span>
        <span class="stat-value">{{ store.result.total_beads.toLocaleString() }}</span>
      </div>
    </div>

    <!-- Action toolbar -->
    <div class="color-actions">
      <button class="action-btn" :class="{ active: mode === 'highlight' }"
        @click="toggleMode('highlight')">
        {{ mode === 'highlight' ? '退出高亮' : '颜色高亮' }}
      </button>
      <button class="action-btn" :class="{ active: mode === 'replace' }"
        @click="toggleMode('replace')">
        {{ mode === 'replace' ? '退出替换' : '替换杂色' }}
      </button>
      <button v-if="Object.keys(store.replaceColors).length > 0 && !store.replaceColors._source"
        class="action-btn reset-action" @click="store.resetReplaceColors()">
        重置替换
      </button>
    </div>

    <!-- Mode hint -->
    <p v-if="mode === 'highlight'" class="mode-hint">点击色块高亮显示在图上</p>
    <p v-else-if="mode === 'replace'" class="mode-hint">点击要替换的色块</p>
    <p v-else-if="!store.cardUnlocked" class="mode-hint">点击色块可去除杂色（需卡密解锁）</p>
    <p v-else-if="store.excludedColors.length === 0" class="mode-hint">点击色块可去除杂色</p>

    <table class="color-table">
      <thead>
        <tr>
          <th>色块</th>
          <th>色号</th>
          <th>颜色名称</th>
          <th style="text-align: right">数量</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="c in store.result.colors_used" :key="c.code"
          :class="{
            excluded: isExcluded(c.index),
            clickable: store.cardUnlocked || mode,
            highlighted: isHighlighted(c.index),
            'replace-source': isReplaced(c.index)
          }"
          @click="handleRowClick(c)">
          <td>
            <span class="color-swatch" :style="{ backgroundColor: c.hex }"></span>
            <span v-if="isExcluded(c.index)" class="excluded-mark">&#10005;</span>
            <span v-if="isHighlighted(c.index)" class="highlight-mark">&#9733;</span>
            <span v-if="isReplaced(c.index)" class="replace-mark">&#8594;{{ getReplaceTargetCode(c.index) }}</span>
          </td>
          <td>{{ c.code }}</td>
          <td>{{ c.name }}</td>
          <td class="count">{{ c.count.toLocaleString() }}</td>
        </tr>
        <tr class="total-row">
          <td colspan="3">合计</td>
          <td class="count">{{ store.result.total_beads.toLocaleString() }}</td>
        </tr>
      </tbody>
    </table>

    <!-- Replace color modal -->
    <ReplaceColorModal
      :visible="showReplaceModal"
      :source-color="replaceSource"
      :palette-colors="paletteColorList"
      @close="closeReplaceModal"
      @select="onReplaceSelect" />
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useAppStore } from '../stores/app.js'
import { fetchPaletteDetail } from '../api/index.js'
import ReplaceColorModal from './ReplaceColorModal.vue'

const store = useAppStore()
const mode = ref(null)
const showReplaceModal = ref(false)
const replaceSource = ref({ hex: '', name: '', code: '', index: 0 })
const paletteColorList = ref([])

function toggleMode(newMode) {
  if (mode.value === newMode) {
    mode.value = null
    if (newMode === 'highlight') store.clearHighlight()
  } else {
    mode.value = newMode
    if (newMode === 'highlight') store.clearHighlight()
  }
}

async function handleRowClick(c) {
  const idx = c.index - 1
  if (mode.value === 'highlight') {
    store.setHighlight(idx)
  } else if (mode.value === 'replace') {
    // Open modal
    replaceSource.value = c
    try {
      const detail = await fetchPaletteDetail(store.selectedPaletteId)
      const entries = Object.entries(detail.colors)
      // Filter out excluded colors, keep original indices
      const excluded = store.excludedColors || []
      paletteColorList.value = entries
        .map(([code, v], i) => ({ code, hex: v.hex, name: v.name, index: i + 1 }))
        .filter((_, i) => !excluded.includes(i))
    } catch (e) {
      // Fallback: use colors from result
      paletteColorList.value = store.result.colors_used.map(cc => ({
        code: cc.code,
        hex: cc.hex,
        name: cc.name,
        index: cc.index,
      }))
    }
    showReplaceModal.value = true
  } else if (store.cardUnlocked) {
    store.excludeColor(idx)
  }
}

function closeReplaceModal() {
  showReplaceModal.value = false
}

function onReplaceSelect(targetColor) {
  const srcIdx = replaceSource.value.index - 1
  const tgtIdx = targetColor.index - 1
  const newReplace = { ...store.replaceColors }
  delete newReplace._source
  newReplace[srcIdx] = tgtIdx
  store.replaceColors = newReplace
  store.scheduleGenerate()
  showReplaceModal.value = false
}

function isExcluded(displayIndex) {
  return store.excludedColors.includes(displayIndex - 1)
}

function isHighlighted(displayIndex) {
  return store.highlightIndex === displayIndex - 1
}

function isReplaced(displayIndex) {
  const idx = displayIndex - 1
  return idx in store.replaceColors && store.replaceColors[idx] !== undefined
}

function getReplaceTargetCode(displayIndex) {
  const idx = displayIndex - 1
  const targetIdx = store.replaceColors[idx]
  if (targetIdx !== undefined) {
    return String(targetIdx + 1).padStart(2, '0')
  }
  return ''
}
</script>
