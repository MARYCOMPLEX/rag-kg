<script setup lang="ts">
import { NCheckbox } from 'naive-ui'
import { useId } from 'vue'

defineProps<{
  label?: string;
  disabled?: boolean;
  indeterminate?: boolean;
}>()

const value = defineModel<boolean>('value')
const checkboxId = useId()
</script>

<template>
  <div class="flex items-center">
    <n-checkbox
      :id="checkboxId"
      v-model:checked="value"
      :disabled="disabled"
      :indeterminate="indeterminate"
      class="base-checkbox"
    />
    <label 
      v-if="label" 
      :for="checkboxId"
      class="ml-2 text-[13px] leading-[15.7px] text-text-primary cursor-pointer select-none"
      :class="{ 'text-text-disabled cursor-not-allowed': disabled }"
    >
      {{ label }}
    </label>
  </div>
</template>

<style scoped>
.base-checkbox {
  --n-size: 16px;
  --n-border-radius: var(--radius-xs);
  --n-color: var(--color-surface-container-lowest);
  --n-border: 1px solid var(--color-border-field);
  --n-border-focus: 1px solid var(--color-brand-400-exact);
  --n-box-shadow-focus: var(--shadow-focus);
  
  --n-color-checked: var(--color-primary-container);
  --n-border-checked: 1px solid var(--color-primary-container);
  
  /* Disabled state */
  --n-color-disabled: var(--color-bg-disabled);
  --n-border-disabled: 1px solid transparent;
  --n-color-disabled-checked: var(--color-bg-disabled);
  --n-border-disabled-checked: 1px solid transparent;
  --n-check-mark-color-disabled: var(--color-text-tertiary);
  --n-check-mark-color-disabled-checked: var(--color-text-tertiary);
}

:deep(.n-checkbox-box) {
  transition: all var(--motion-duration-fast) var(--motion-ease-standard);
}
:deep(.n-checkbox-icon) {
  stroke-width: 1.5; /* Note: internal svg might not perfectly adopt this, but we try */
  transition: stroke-dashoffset var(--motion-duration-fast) var(--motion-ease-standard);
}

/* Hover state overrides */
:deep(.n-checkbox:not(.n-checkbox--disabled):hover .n-checkbox-box) {
  border: 1px solid var(--color-brand-400-exact);
}
:deep(.n-checkbox.n-checkbox--checked:not(.n-checkbox--disabled):hover .n-checkbox-box) {
  border: 1px solid var(--color-primary-container);
}
</style>
