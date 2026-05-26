<script setup lang="ts">
import { NInput } from 'naive-ui'
import { computed, useId } from 'vue'

const props = defineProps<{
  label?: string;
  placeholder?: string;
  error?: string;
  shortcut?: string;
  disabled?: boolean;
  type?: 'text' | 'password';
}>()

const value = defineModel<string>('value')
const inputId = useId()

const hasError = computed(() => !!props.error)
</script>

<template>
  <div class="flex flex-col w-full relative">
    <!-- Label (meta 11/13.3) -->
    <label 
      v-if="label" 
      :for="inputId"
      class="text-[11px] leading-[13.3px] font-medium text-text-tertiary uppercase tracking-widest mb-1"
    >
      {{ label }}
    </label>
    
    <!-- Input wrapper -->
    <n-input
      :id="inputId"
      v-model:value="value"
      :type="type || 'text'"
      :placeholder="placeholder"
      :disabled="disabled"
      :status="hasError ? 'error' : undefined"
      class="base-input"
      :class="{ 'is-error': hasError, 'is-disabled': disabled }"
    >
      <template #prefix v-if="$slots.prefix">
        <slot name="prefix"></slot>
      </template>

      <!-- Suffix (Shortcut badge or custom slot) -->
      <template #suffix>
        <slot name="suffix">
          <div 
            v-if="shortcut" 
            class="input-shortcut-badge flex items-center justify-center bg-bg-subtle text-text-tertiary font-mono text-[11px] leading-none w-6 h-5"
            aria-hidden="true"
          >
            {{ shortcut }}
          </div>
        </slot>
      </template>
    </n-input>

    <!-- Helper / Error text -->
    <div 
      v-if="error" 
      class="input-error-message text-[13px] leading-[15.7px] mt-1 min-h-[16px]"
      role="alert"
      aria-live="polite"
    >
      {{ error }}
    </div>
  </div>
</template>

<style scoped>
.base-input {
  --n-height: 40px;
  --n-border-radius: var(--radius-field);
  --n-font-size: 14px;
  --n-padding-left: 12px;
  --n-padding-right: 14px;
  --n-color: var(--color-bg-surface);
  --n-color-focus: var(--color-bg-surface);
  --n-text-color: var(--color-text-primary);
  --n-border: 1px solid var(--color-border);
  --n-border-hover: 1px solid var(--color-border); /* Same as default unless focused */
  transition:
    border-color var(--motion-duration-fast) var(--motion-ease-standard),
    box-shadow var(--motion-duration-fast) var(--motion-ease-standard);
}

.input-shortcut-badge {
  border-radius: var(--radius-sm);
}

.input-error-message {
  color: var(--color-danger-700-exact);
}

:deep(.n-input__input-el) {
  caret-color: var(--color-brand-500);
  line-height: 16.9px;
}
:deep(.n-input__placeholder) {
  color: var(--color-text-tertiary) !important;
}

/* Hover and Focus Overrides */
:deep(.n-input:not(.is-disabled):hover) {
  --n-border-hover: 1px solid var(--color-brand-500);
}
:deep(.n-input:not(.is-disabled).n-input--focus) {
  --n-border-focus: 1px solid var(--color-brand-500);
  --n-box-shadow-focus: var(--shadow-focus);
}

/* Error Overrides */
:deep(.n-input.is-error:not(.is-disabled)) {
  --n-border: 1px solid var(--color-danger-500);
  --n-border-hover: 1px solid var(--color-danger-500);
}
:deep(.n-input.is-error:not(.is-disabled).n-input--focus) {
  --n-border-focus: 1px solid var(--color-danger-500);
  --n-box-shadow-focus: var(--shadow-focus-danger);
}

/* Disabled Overrides */
.base-input.is-disabled {
  --n-color-disabled: var(--color-bg-subtle) !important;
  --n-border-disabled: 1px solid var(--color-border) !important;
  --n-text-color-disabled: var(--color-text-disabled) !important;
}
:deep(.base-input.is-disabled .n-input__placeholder) {
  color: var(--color-text-disabled) !important;
}
</style>
