<script setup lang="ts">
import { NRadio } from 'naive-ui'
import { useId } from 'vue'

const props = defineProps<{
  label?: string;
  valueOption?: string | number | boolean;
  disabled?: boolean;
}>()

const checked = defineModel<string | number | boolean | null>('checked')
const radioId = useId()

function updateChecked(isChecked: boolean) {
  if (isChecked)
    checked.value = props.valueOption ?? null
}
</script>

<template>
  <div class="flex items-center">
    <n-radio
      :id="radioId"
      :value="valueOption"
      :checked="checked === valueOption"
      :disabled="disabled"
      class="base-radio"
      :name="radioId /* Temporary fix for roving tabindex if needed, usually managed by RadioGroup */"
      @update:checked="updateChecked"
    />
    <label 
      v-if="label" 
      :for="radioId"
      class="ml-2 text-[13px] leading-[15.7px] text-text-primary cursor-pointer select-none"
      :class="{ 'text-text-disabled cursor-not-allowed': disabled }"
    >
      {{ label }}
    </label>
  </div>
</template>

<style scoped>
.base-radio {
  --n-radio-size: 16px;
  --n-color: var(--color-surface-container-lowest);
  --n-border: 1px solid var(--color-border-field);
  --n-border-focus: 1px solid var(--color-brand-400-exact);
  --n-box-shadow-focus: var(--shadow-focus);
  
  --n-color-active: var(--color-surface-container-lowest);
  --n-border-active: 1.5px solid var(--color-primary-container);
  --n-dot-color-active: var(--color-primary-container);
  /* Dot size is controlled via n-radio inner styling, usually proportional. We'll add a transform if needed */
  
  /* Disabled state */
  --n-color-disabled: var(--color-bg-disabled);
  --n-border-disabled: 1px solid transparent;
  --n-dot-color-disabled: var(--color-text-tertiary);
}

:deep(.n-radio__dot) {
  transition: all var(--motion-duration-fast) var(--motion-ease-standard);
}
:deep(.n-radio__dot::before) {
  /* inner dot scaling */
  transition:
    transform var(--motion-duration-spring) var(--motion-ease-spring),
    background-color var(--motion-duration-fast) var(--motion-ease-standard);
}

/* Hover state */
:deep(.n-radio:not(.n-radio--disabled):hover .n-radio__dot) {
  border: 1px solid var(--color-brand-400-exact);
}
:deep(.n-radio.n-radio--checked:not(.n-radio--disabled):hover .n-radio__dot) {
  border: 1.5px solid var(--color-primary-container);
}
</style>
