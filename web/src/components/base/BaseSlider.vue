<script setup lang="ts">
import { NSlider } from 'naive-ui'
import { computed, useId } from 'vue'

defineProps<{
  label?: string;
  min?: number;
  max?: number;
  step?: number;
  disabled?: boolean;
  marks?: Record<number, string>;
  showBadge?: boolean;
}>()

const value = defineModel<number>('value', { default: 0 })
const sliderId = useId()

const displayValue = computed(() => {
  return value.value.toFixed(2)
})
</script>

<template>
  <div class="flex flex-col w-full relative">
    <div class="flex justify-between items-end mb-2">
      <label 
        v-if="label" 
        :for="sliderId"
        class="text-[11px] leading-[13.3px] font-medium text-text-tertiary uppercase tracking-widest"
      >
        {{ label }}
      </label>
      
      <!-- Value Badge for continuous sliders -->
      <div 
        v-if="showBadge"
        class="slider-value-badge bg-info-50 text-info-700 px-1.5 py-0.5 font-mono text-[13px] leading-[20px]"
        aria-live="polite"
      >
        {{ displayValue }}
      </div>
    </div>

    <div class="w-[232px] pt-1 pb-2">
      <n-slider
        :id="sliderId"
        v-model:value="value"
        :min="min || 0"
        :max="max || 100"
        :step="step || 1"
        :marks="marks"
        :disabled="disabled"
        :tooltip="false"
        class="base-slider"
        :class="{ 'is-disabled': disabled }"
      />
    </div>
  </div>
</template>

<style scoped>
.base-slider {
  --n-rail-height: 4px;
  --n-handle-size: 16px;
  --n-rail-color: var(--color-bg-disabled);
  --n-rail-color-hover: var(--color-bg-disabled);
  --n-fill-color: var(--color-primary-container);
  --n-fill-color-hover: var(--color-primary-container);
  --n-handle-color: var(--color-surface-container-lowest);
  --n-handle-border: 1.5px solid var(--color-primary-container);
  --n-handle-box-shadow: var(--shadow-xs);
  --n-handle-box-shadow-hover: var(--shadow-xs);
  --n-handle-box-shadow-active: var(--shadow-xs);
  --n-handle-box-shadow-focus: var(--shadow-focus);
}

.slider-value-badge {
  border-radius: var(--radius-sm);
}

:deep(.n-slider-handle) {
  transition:
    transform var(--motion-duration-fast) var(--motion-ease-standard),
    box-shadow var(--motion-duration-fast) var(--motion-ease-standard);
}

/* Hover Scale */
:deep(.n-slider:not(.is-disabled) .n-slider-handle:hover) {
  transform: translateX(-50%) translateY(-50%) scale(1.1);
}

/* Dragging Scale */
:deep(.n-slider:not(.is-disabled).n-slider--active .n-slider-handle) {
  transform: translateX(-50%) translateY(-50%) scale(1.15);
}

/* Hit Area Expansion via pseudo-element */
:deep(.n-slider-handle::after) {
  content: '';
  position: absolute;
  top: -8px;
  bottom: -8px;
  left: -8px;
  right: -8px;
  background: transparent;
  border-radius: var(--radius-pill);
}

/* Disabled State overrides */
.base-slider.is-disabled {
  --n-rail-color: var(--color-bg-disabled) !important;
  --n-fill-color: var(--color-text-disabled) !important;
  --n-handle-border: 1.5px solid var(--color-border-field) !important;
  --n-handle-color: var(--color-bg-hover) !important;
  --n-handle-box-shadow: var(--shadow-none) !important;
}
</style>
