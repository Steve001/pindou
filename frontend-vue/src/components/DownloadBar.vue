<template>
  <div class="download-bar">
    <button class="btn btn-secondary btn-sm" @click="downloadPNG">
      下载图纸 (PNG)
    </button>
    <button class="btn btn-secondary btn-sm" @click="store.exportPDF()">
      下载图纸 (PDF)
    </button>
  </div>
</template>

<script setup>
import { useAppStore } from '../stores/app.js'

const store = useAppStore()

function downloadPNG() {
  if (!store.result) return
  const link = document.createElement('a')
  link.href = `data:image/png;base64,${store.result.image_base64}`
  link.download = `bead-pattern-${Date.now()}.png`
  link.click()
}
</script>
