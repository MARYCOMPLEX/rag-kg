<script setup lang="ts">
import { NSwitch } from 'naive-ui'
import { useId } from 'vue'

defineProps<{
  label?: string;
  disabled?: boolean;
}>()

const value = defineModel<boolean>('value')
const switchId = useId()
</script>

<template>
  <div class="flex items-center">
    <n-switch
      :id="switchId"
      v-model:value="value"
      :disabled="disabled"
      class="base-toggle"
    />
    <label 
      v-if="label" 
      :for="switchId"
      class="ml-2 text-[13px] leading-[15.7px] text-text-primary cursor-pointer select-none"
      :class="{ 'text-text-disabled cursor-not-allowed': disabled }"
    >
      {{ label }}
    </label>
  </div>
</template>

<style scoped>
.base-toggle {
  --n-rail-width: 32px;
  --n-rail-height: 18px;
  --n-button-width: 14px;
  --n-button-height: 14px;
  
  --n-rail-color: var(--color-bg-disabled);
  --n-button-color: var(--color-surface-container-lowest);
  --n-rail-color-active: var(--color-primary-container);
  
  --n-box-shadow-focus: var(--shadow-focus);
  
  /* Disabled state */
  --n-rail-color-disabled: var(--color-bg-hover);
  --n-button-color-disabled: var(--color-canvas);
  --n-rail-color-active-disabled: var(--color-bg-hover);
  --n-button-color-active-disabled: var(--color-canvas);
}

:deep(.n-switch__rail) {
  transition: background-color var(--motion-duration-modal) var(--motion-ease-standard);
}
:deep(.n-switch__button) {
  transition:
    transform var(--motion-duration-modal) var(--motion-ease-standard),
    background-color var(--motion-duration-modal) var(--motion-ease-standard);
}

/* Hover override for the track when off */
:deep(.n-switch:not(.n-switch--disabled):not(.n-switch--active):hover .n-switch__rail) {
  background-color: var(--color-text-tertiary);
}
</style>
