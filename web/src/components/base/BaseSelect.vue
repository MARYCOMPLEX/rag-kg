<script setup lang="ts">
import { NSelect } from 'naive-ui'
import { useId, h } from 'vue'

interface SelectOption {
  label: string;
  value: string | number;
  count?: number;
  tone?: string;
  [key: string]: any;
}

defineProps<{
  label?: string;
  options: SelectOption[];
  placeholder?: string;
  disabled?: boolean;
}>()

const value = defineModel<string | number | null>('value')
const selectId = useId()

// KG Entity Tones
const toneColorMap: Record<string, string> = {
  concept: 'var(--color-kg-concept)',
  method: 'var(--color-kg-method)',
  dataset: 'var(--color-kg-dataset)',
  metric: 'var(--color-kg-metric)',
  author: 'var(--color-kg-author)',
  venue: 'var(--color-kg-venue)',
}

const renderLabel = (option: SelectOption) => {
  return h('div', { class: 'flex items-center w-full min-w-0' }, [
    // Leading dot if tone is provided
    option.tone ? h('div', { 
      class: 'w-3 h-3 flex-shrink-0 mr-3', 
      style: { backgroundColor: toneColorMap[option.tone] || 'var(--color-kg-concept)', borderRadius: 'var(--radius-pill)' } 
    }) : null,
    
    // Label text
    h('span', { class: 'text-[14px] text-text-primary truncate flex-grow' }, option.label),
    
    // Trailing mono count if provided
    option.count !== undefined ? h('span', { 
      class: 'font-mono text-[11px] text-text-tertiary tabular-nums ml-3 flex-shrink-0'
    }, `${option.count.toLocaleString()} docs`) : null
  ])
}
</script>

<template>
  <div class="flex flex-col w-full relative">
    <label 
      v-if="label" 
      :for="selectId"
      class="text-[11px] leading-[13.3px] font-medium text-text-tertiary uppercase tracking-widest mb-1"
    >
      {{ label }}
    </label>

    <n-select
      :id="selectId"
      v-model:value="value"
      :options="options"
      :render-label="renderLabel"
      :placeholder="placeholder"
      :disabled="disabled"
      class="base-select"
      :class="{ 'is-disabled': disabled }"
      :menu-props="{ class: 'base-select-menu' }"
    />
  </div>
</template>

<style scoped>
.base-select {
  --n-border-radius: var(--radius-field);
  /* Naive overrides height in theme.ts to 36px */
  --n-color: var(--color-surface-container-lowest);
  --n-color-focus: var(--color-surface-container-lowest);
  --n-text-color: var(--color-neutral-900);
  --n-border: 1px solid var(--color-border-field);
  --n-border-hover: 1px solid var(--color-border-strong);
  --n-color-hover: var(--color-bg-hover);
  
  --n-border-focus: 1px solid var(--color-primary-container);
  --n-box-shadow-focus: var(--shadow-focus);
  --n-border-active: 1px solid var(--color-primary-container);
  --n-box-shadow-active: var(--shadow-focus);
  transition: all var(--motion-duration-fast) var(--motion-ease-standard);
}

:deep(.n-base-selection:not(.n-base-selection--disabled):hover) {
  background-color: var(--color-bg-hover) !important;
}

:deep(.n-base-selection__placeholder) {
  color: var(--color-text-tertiary) !important;
}

/* Disabled */
.base-select.is-disabled {
  --n-color-disabled: var(--color-bg-hover) !important;
  --n-border-disabled: 1px solid var(--color-border-field) !important;
  --n-text-color-disabled: var(--color-text-disabled) !important;
}
:deep(.base-select.is-disabled .n-base-selection__placeholder) {
  color: var(--color-text-disabled) !important;
}
</style>

<style>
/* Global styles for the detached menu */
.base-select-menu {
  border-radius: var(--radius-popover) !important;
  box-shadow: var(--shadow-lg) !important;
  padding: 4px !important;
}

.base-select-menu .n-base-select-option {
  padding: 0 12px !important;
  height: 36px !important;
  display: flex;
  align-items: center;
  border-radius: var(--radius-sm);
  position: relative;
  transition: background-color var(--motion-duration-fast) var(--motion-ease-standard);
}

.base-select-menu .n-base-select-option:hover {
  background-color: var(--color-bg-hover) !important;
}

.base-select-menu .n-base-select-option.n-base-select-option--selected {
  background-color: var(--color-brand-100) !important;
}

/* 2px solid left border simulation for selected item */
.base-select-menu .n-base-select-option.n-base-select-option--selected::before {
  content: '';
  position: absolute;
  left: 0;
  top: 4px;
  bottom: 4px;
  width: 2px;
  background-color: var(--color-primary-container);
  border-radius: 0 var(--radius-2xs) var(--radius-2xs) 0;
}
</style>
