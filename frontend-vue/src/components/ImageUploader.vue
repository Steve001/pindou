<template>
  <div class="card">
    <h3>上传图片</h3>
    <div
      class="upload-area"
      :class="{ dragover }"
      @click="!cropping && fileInput.click()"
      @dragover.prevent="dragover = true"
      @dragleave="dragover = false"
      @drop.prevent="onDrop"
    >
      <input
        ref="fileInput"
        type="file"
        accept="image/*"
        @change="onFileChange"
      />
      <div v-if="!store.uploadedPreviewUrl">
        <div class="upload-icon">&#128247;</div>
        <p class="upload-text">
          <strong>点击选择</strong> 或拖拽图片到此处
        </p>
        <p class="form-hint">支持 JPG、PNG，最大 10MB</p>
      </div>
      <div v-else-if="!cropping">
        <img :src="store.uploadedPreviewUrl" class="upload-preview" alt="预览" />
        <p class="form-hint" style="margin-top: 8px">点击或拖拽更换图片</p>
      </div>
    </div>

    <!-- Crop toolbar -->
    <div v-if="store.uploadedPreviewUrl && !cropping" class="crop-toolbar">
      <button class="action-btn" @click="startCrop">裁剪图片</button>
      <button class="action-btn" @click="doRemoveBg" :disabled="removingBg">
        {{ removingBg ? '抠图中...' : '智能抠图' }}
      </button>
    </div>

    <!-- Crop overlay -->
    <div v-if="cropping" class="crop-container">
      <div class="crop-image-wrap" ref="cropWrap"
        @mousedown="onCropMouseDown"
        @mousemove="onCropMouseMove"
        @mouseup="onCropMouseUp"
        @mouseleave="onCropMouseUp">
        <img :src="store.uploadedPreviewUrl" class="crop-image" @load="onCropImageLoad" ref="cropImg" />
        <!-- Dark overlay -->
        <div class="crop-overlay" :style="overlayStyle"></div>
        <!-- Selection box -->
        <div class="crop-selection" :style="selectionStyle"></div>
        <!-- Edge overlays -->
        <div class="crop-dim" :style="{ top: 0, left: 0, right: 0, height: cropRect.y + 'px' }"></div>
        <div class="crop-dim" :style="{ top: (cropRect.y + cropRect.h) + 'px', left: 0, right: 0, bottom: 0 }"></div>
        <div class="crop-dim" :style="{ top: cropRect.y + 'px', left: 0, width: cropRect.x + 'px', height: cropRect.h + 'px' }"></div>
        <div class="crop-dim" :style="{ top: cropRect.y + 'px', left: (cropRect.x + cropRect.w) + 'px', right: 0, height: cropRect.h + 'px' }"></div>
      </div>
      <div class="crop-actions">
        <button class="btn btn-primary btn-sm" @click="applyCrop">确认裁剪</button>
        <button class="btn btn-secondary btn-sm" @click="cancelCrop">取消</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useAppStore } from '../stores/app.js'

const store = useAppStore()
const fileInput = ref(null)
const dragover = ref(false)
const cropping = ref(false)
const removingBg = ref(false)
const cropWrap = ref(null)
const cropImg = ref(null)

const cropRect = ref({ x: 0, y: 0, w: 0, h: 0 })
const dragging = ref(false)
const dragStart = ref({ x: 0, y: 0 })
const displaySize = ref({ w: 0, h: 0 })

function onFileChange(e) {
  const file = e.target.files[0]
  if (file && file.type.startsWith('image/')) {
    store.setFile(file)
  }
}

function onDrop(e) {
  dragover.value = false
  const file = e.dataTransfer.files[0]
  if (file && file.type.startsWith('image/')) {
    store.setFile(file)
  }
}

async function doRemoveBg() {
  removingBg.value = true
  try {
    await store.removeBg()
  } finally {
    removingBg.value = false
  }
}

function startCrop() {
  cropping.value = true
}

function onCropImageLoad() {
  const img = cropImg.value
  displaySize.value = { w: img.clientWidth, h: img.clientHeight }
  cropRect.value = {
    x: img.clientWidth * 0.1,
    y: img.clientHeight * 0.1,
    w: img.clientWidth * 0.8,
    h: img.clientHeight * 0.8,
  }
}

function getPos(e) {
  const wrap = cropWrap.value
  const rect = wrap.getBoundingClientRect()
  return { x: e.clientX - rect.left, y: e.clientY - rect.top }
}

function onCropMouseDown(e) {
  e.preventDefault()
  dragging.value = true
  const pos = getPos(e)
  dragStart.value = pos
  cropRect.value = { x: pos.x, y: pos.y, w: 0, h: 0 }
}

function onCropMouseMove(e) {
  if (!dragging.value) return
  const pos = getPos(e)
  const img = cropImg.value
  const x = Math.max(0, Math.min(dragStart.value.x, pos.x))
  const y = Math.max(0, Math.min(dragStart.value.y, pos.y))
  const w = Math.min(Math.abs(pos.x - dragStart.value.x), img.clientWidth - x)
  const h = Math.min(Math.abs(pos.y - dragStart.value.y), img.clientHeight - y)
  cropRect.value = { x, y, w, h }
}

function onCropMouseUp() {
  dragging.value = false
}

const selectionStyle = computed(() => ({
  left: cropRect.value.x + 'px',
  top: cropRect.value.y + 'px',
  width: cropRect.value.w + 'px',
  height: cropRect.value.h + 'px',
}))

const overlayStyle = computed(() => ({
  display: cropRect.value.w > 0 ? 'block' : 'none',
}))

function applyCrop() {
  const img = cropImg.value
  const { w: dw, h: dh } = displaySize.value
  const natW = img.naturalWidth
  const natH = img.naturalHeight
  const scaleX = natW / dw
  const scaleY = natH / dh

  const sx = Math.round(cropRect.value.x * scaleX)
  const sy = Math.round(cropRect.value.y * scaleY)
  const sw = Math.round(cropRect.value.w * scaleX)
  const sh = Math.round(cropRect.value.h * scaleY)

  if (sw < 5 || sh < 5) {
    cancelCrop()
    return
  }

  const canvas = document.createElement('canvas')
  canvas.width = sw
  canvas.height = sh
  const ctx = canvas.getContext('2d')
  ctx.drawImage(img, sx, sy, sw, sh, 0, 0, sw, sh)

  canvas.toBlob((blob) => {
    const file = new File([blob], 'cropped.png', { type: 'image/png' })
    store.setFile(file)
    cropping.value = false
  }, 'image/png')
}

function cancelCrop() {
  cropping.value = false
}
</script>
