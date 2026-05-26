<script setup lang="ts">
import { NInput } from 'naive-ui'
import { computed, useId, ref } from 'vue'

const props = defineProps<{
  label?: string;
  placeholder?: string;
  error?: string;
  disabled?: boolean;
  maxlength?: number;
  showCount?: boolean;
}>()

const value = defineModel<string>('value', { default: '' })
const inputId = useId()
const textareaRef = ref(null)

const hasError = computed(() => !!props.error)
const charCount = computed(() => value.value.length)
const charsRemaining = computed(() => props.maxlength ? props.maxlength - charCount.value : null)

const isWarning = computed(() => charsRemaining.value !== null && charsRemaining.value < 20 && charsRemaining.value >= 0)
const isOverflow = computed(() => charsRemaining.value !== null && charsRemaining.value < 0)

const onKeydown = (e: KeyboardEvent) => {
  // Prevent default Enter behavior and emit for Cmd+Enter
  if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
    // Parent should listen to @submit if needed
  }
}
</script>

<template>
  <div class="flex flex-col w-full relative">
    <!-- Label -->
    <label 
      v-if="label" 
      :for="inputId"
      class="text-[11px] leading-[13.3px] font-medium text-text-tertiary uppercase tracking-widest mb-1"
    >
      {{ label }}
    </label>
    
    <!-- Textarea wrapper -->
    <n-input
      ref="textareaRef"
      :id="inputId"
      v-model:value="value"
      type="textarea"
      :placeholder="placeholder"
      :disabled="disabled"
      :status="hasError ? 'error' : undefined"
      class="base-textarea"
      :class="{ 'is-error': hasError, 'is-disabled': disabled }"
      :autosize="{ minRows: 5, maxRows: 10 }"
      @keydown="onKeydown"
    />

    <!-- Bottom Row: Error and Counter -->
    <div class="flex justify-between items-start mt-1 min-h-[16px]">
      <div 
        v-if="error" 
        class="textarea-error-message text-[13px] leading-[15.7px]"
        role="alert"
        aria-live="polite"
      >
        {{ error }}
      </div>
      <div v-else></div>

      <div 
        v-if="showCount && maxlength" 
        class="font-mono text-[12px] leading-[14.5px] text-right"
        :class="{
          'text-text-tertiary': !isWarning && !isOverflow,
          'text-warning-700': isWarning,
          'text-danger-700': isOverflow
        }"
      >
        {{ charCount }} / {{ maxlength }}
      </div>
    </div>
  </div>
</template>

<style scoped>
/* Grow 120ms ease-out, Shrink immediate */
.base-textarea {
  --n-border-radius: var(--radius-dialog);
  --n-font-size: 14px;
  --n-padding-left: 14px; /* padding 12/14 mapping: top/bottom 12, left/right 14 roughly */
  --n-padding-right: 14px;
  --n-padding-top: 12px;
  --n-padding-bottom: 12px;
  --n-color: var(--color-bg-surface);
  --n-color-focus: var(--color-bg-surface);
  --n-text-color: var(--color-text-primary);
  --n-border: 1px solid var(--color-border);
  --n-border-hover: 1px solid var(--color-border);
  transition:
    border-color var(--motion-duration-fast) var(--motion-ease-standard),
    box-shadow var(--motion-duration-fast) var(--motion-ease-standard),
    height var(--motion-duration-fast) var(--motion-ease-standard);
}

.textarea-error-message {
  color: var(--color-danger-700-exact);
}

:deep(.n-input__textarea-el) {
  caret-color: var(--color-brand-500);
  line-height: 16.9px;
  min-height: 120px;
  max-height: 240px;
  resize: none !important; /* Disable native resize */
}

/* Force shrink immediate using a trick, or just rely on DOM for height changes */

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
.base-textarea.is-disabled {
  --n-color-disabled: var(--color-bg-subtle) !important;
  --n-border-disabled: 1px solid var(--color-border) !important;
  --n-text-color-disabled: var(--color-text-disabled) !important;
}
:deep(.base-textarea.is-disabled .n-input__placeholder) {
  color: var(--color-text-disabled) !important;
}
</style>
