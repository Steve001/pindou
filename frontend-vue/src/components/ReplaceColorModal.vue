<template>
  <div v-if="visible" class="modal-overlay" @click.self="$emit('close')">
    <div class="modal-card">
      <div class="modal-header">
        <h3>调整为其他颜色</h3>
        <button class="modal-close" @click="$emit('close')">&times;</button>
      </div>
      <div class="modal-body">
        <div class="source-color-info">
          <span class="color-swatch-lg" :style="{ backgroundColor: sourceColor.hex }"></span>
          <span class="source-label">{{ sourceColor.code }} - {{ sourceColor.name }}</span>
          <span class="arrow-icon">&#8594;</span>
        </div>
        <div class="color-grid">
          <div v-for="c in paletteColors" :key="c.code"
            class="color-option"
            :class="{ active: c.code === sourceColor.code }"
            @click="selectColor(c)">
            <span class="color-swatch-lg" :style="{ backgroundColor: c.hex }"></span>
            <span class="color-code">{{ c.code }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { defineProps, defineEmits } from 'vue'

const props = defineProps({
  visible: Boolean,
  sourceColor: Object,
  paletteColors: Array,
})

const emit = defineEmits(['close', 'select'])

function selectColor(color) {
  emit('select', color)
}
</script>
