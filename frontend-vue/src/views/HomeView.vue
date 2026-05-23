<template>
  <main class="main-content">
    <div class="container">
      <div v-if="store.error" class="error-banner">
        <span>{{ store.error }}</span>
        <button @click="store.clearError()">&times;</button>
      </div>

      <div class="main-grid">
        <!-- Left: Settings -->
        <div class="settings-panel">
          <ImageUploader />

          <div class="card">
            <h3>生成设置</h3>

            <!-- Brightness -->
            <div class="slider-group">
              <div class="slider-row">
                <label>亮度</label>
                <span class="slider-val">{{ store.brightness.toFixed(1) }}</span>
              </div>
              <input type="range" min="0.1" max="3.0" step="0.1"
                :value="store.brightness"
                @input="store.brightness = parseFloat($event.target.value); store.scheduleGenerate()" />
            </div>

            <!-- Contrast -->
            <div class="slider-group">
              <div class="slider-row">
                <label>对比度</label>
                <span class="slider-val">{{ store.contrast.toFixed(1) }}</span>
              </div>
              <input type="range" min="0.1" max="3.0" step="0.1"
                :value="store.contrast"
                @input="store.contrast = parseFloat($event.target.value); store.scheduleGenerate()" />
            </div>

            <!-- Saturation -->
            <div class="slider-group">
              <div class="slider-row">
                <label>饱和度</label>
                <span class="slider-val">{{ store.saturation.toFixed(1) }}</span>
              </div>
              <input type="range" min="0.1" max="3.0" step="0.1"
                :value="store.saturation"
                @input="store.saturation = parseFloat($event.target.value); store.scheduleGenerate()" />
            </div>

            <!-- Palette -->
            <div class="form-group">
              <label for="palette">色板品牌</label>
              <select id="palette" v-model="store.selectedPaletteId"
                @change="store.scheduleGenerate()">
                <option v-for="p in store.palettes" :key="p.id" :value="p.id">
                  {{ p.name }}
                </option>
              </select>
              <p class="form-hint">不同品牌色号颜色不同，请根据手头珠子选择</p>
            </div>

            <!-- Color merge value -->
            <div class="slider-group">
              <div class="slider-row">
                <label>颜色合并值</label>
                <span class="slider-val">{{ store.mergeValue }}</span>
              </div>
              <input type="range" min="0" max="100" step="1"
                :value="store.mergeValue"
                @input="store.mergeValue = parseInt($event.target.value); store.scheduleGenerate()" />
              <p class="form-hint">数值越大相近颜色合并越大，默认0</p>
            </div>

            <!-- Size -->
            <div class="size-settings">
              <div class="size-header">
                <label class="size-label">尺寸设置</label>
              </div>
              <div class="size-row">
                <input type="number" class="size-input" v-model.number="store.gridWidth"
                  :min="1" :max="store.maxGridSize"
                  @change="onWidthChange(); store.scheduleGenerate()" />
                <button class="lock-btn" :class="{ active: store.lockAspectRatio }"
                  @click="store.lockAspectRatio = !store.lockAspectRatio"
                  title="锁定宽高比">
                  {{ store.lockAspectRatio ? '&#128274;' : '&#128275;' }}
                </button>
                <input type="number" class="size-input"
                  :value="store.gridHeight === 0 ? '' : store.gridHeight"
                  placeholder="自动" :min="0" :max="store.maxGridSize"
                  @input="onHeightInput" @change="store.scheduleGenerate()" />
              </div>
              <p class="form-hint">{{ store.cardUnlocked ? '最大 300px' : '预览最大 50px' }}</p>
            </div>

            <!-- Show coordinates -->
            <div class="form-group">
              <label>显示坐标</label>
              <input type="checkbox" :checked="store.showCoords"
                @change="store.showCoords = $event.target.checked; store.scheduleGenerate()" />
            </div>

            <!-- Pixelate -->
            <div class="form-group">
              <label>像素化</label>
              <input type="checkbox" :checked="store.pixelate"
                @change="store.pixelate = $event.target.checked; store.scheduleGenerate()" />
            </div>

            <button class="btn-export" @click="store.generate()">
              <span v-if="store.generating" class="spinner"></span>
              {{ store.generating ? '导出中...' : '导出' }}
            </button>
          </div>

          <!-- Card unlock -->
          <div v-if="store.result && store.locked && !store.cardUnlocked" class="card unlock-card">
            <h3>解锁完整功能</h3>
            <p class="unlock-desc">输入卡密解锁下载和修改</p>
            <div class="unlock-form">
              <input type="text" v-model="store.cardCode" placeholder="输入卡密"
                class="unlock-input" @keyup.enter="store.unlockCard()" />
              <button class="btn btn-primary btn-sm" @click="store.unlockCard()">验证</button>
            </div>
          </div>
        </div>

        <!-- Right: Result -->
        <div class="result-panel">
          <div v-if="!store.result" class="card empty-state">
            <div class="empty-icon">&#127912;</div>
            <p>上传图片，调整设置，点击导出</p>
          </div>

          <template v-else>
            <div class="card">
              <div class="image-viewer">
                <div v-if="store.locked && !store.cardUnlocked" class="lock-overlay">
                  <img :src="'data:image/png;base64,' + store.result.image_base64"
                    class="result-image locked" alt="拼豆图纸预览" />
                  <div class="lock-badge">&#128274; 输入卡密解锁下载</div>
                </div>
                <div v-else class="image-scroll">
                  <img :src="'data:image/png;base64,' + store.result.image_base64"
                    class="result-image" :style="{ width: imageZoom + '%' }"
                    alt="拼豆图纸" />
                </div>
                <div v-if="!store.locked || store.cardUnlocked" class="zoom-bar">
                  <button class="zoom-btn" @click="imageZoom = Math.max(20, imageZoom - 20)">&minus;</button>
                  <span class="zoom-label">{{ imageZoom }}%</span>
                  <button class="zoom-btn" @click="imageZoom = Math.min(200, imageZoom + 20)">+</button>
                </div>
              </div>

              <DownloadBar v-if="store.cardUnlocked" />
            </div>

            <div class="card">
              <h3>颜色统计 &amp; 采购清单
                <button v-if="store.excludedColors.length > 0"
                  class="reset-btn" @click="store.resetExcludedColors()">
                  重置
                </button>
              </h3>
              <ColorStats />
            </div>
          </template>
        </div>
      </div>
    </div>
  </main>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useAppStore } from '../stores/app.js'
import ImageUploader from '../components/ImageUploader.vue'
import ColorStats from '../components/ColorStats.vue'
import DownloadBar from '../components/DownloadBar.vue'

const store = useAppStore()
const imageZoom = ref(100)

function onWidthChange() {
  if (store.gridWidth < 1) store.gridWidth = 1
  if (store.gridWidth > store.maxGridSize) store.gridWidth = store.maxGridSize
}

function onHeightInput(e) {
  const val = parseInt(e.target.value)
  store.gridHeight = isNaN(val) || val === 0 ? 0 : Math.min(val, store.maxGridSize)
}

onMounted(() => {
  store.loadPalettes()
  store.checkCardState()
})
</script>
