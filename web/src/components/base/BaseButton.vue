<script setup lang="ts">
import { NButton } from 'naive-ui'
import { computed } from 'vue'

const props = withDefaults(defineProps<{
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger' | 'link';
  size?: 'sm' | 'md' | 'lg';
  disabled?: boolean;
  loading?: boolean;
  block?: boolean;
}>(), {
  variant: 'secondary',
  size: 'md',
  disabled: false,
  loading: false,
  block: false,
})

defineSlots<{
  default?: () => unknown
  icon?: () => unknown
}>()

const emit = defineEmits<{
  (e: 'click', event: MouseEvent): void
}>()

const typeMap: Record<string, 'primary' | 'default' | 'tertiary' | 'error' | 'info'> = {
  primary: 'primary',
  secondary: 'default',
  ghost: 'tertiary',
  danger: 'error',
  link: 'info',
}
const nType = computed(() => typeMap[props.variant] || 'default')

const isText = computed(() => props.variant === 'link')
const isQuaternary = computed(() => props.variant === 'ghost')

</script>

<template>
  <n-button
    :type="nType"
    :disabled="disabled"
    :loading="loading"
    :block="block"
    :text="isText"
    :quaternary="isQuaternary"
    class="base-button"
    :class="[
      `variant-${variant}`, 
      `size-${size}`,
      { 'is-disabled': disabled }
    ]"
    @click="emit('click', $event)"
  >
    <template #icon v-if="$slots.icon">
      <slot name="icon"></slot>
    </template>
    
    <span class="font-medium whitespace-nowrap">
      <slot></slot>
    </span>
  </n-button>
</template>

<style scoped>
/* Base overrides */
.base-button {
  font-family: var(--un-font-sans);
  --n-border-radius: var(--radius-control);
  transition: all var(--motion-duration-fast) var(--motion-ease-standard);
}

/* Sizing overrides bypassing Naive's default medium/small to ensure exact padding */
.base-button.size-sm {
  height: 32px;
  padding: 0 12px;
  font-size: 13px;
  line-height: 15.7px;
}
.base-button.size-md {
  height: 40px;
  padding: 0 16px;
  font-size: 14px;
  line-height: 16.9px;
}
.base-button.size-lg {
  height: 48px;
  padding: 0 20px;
  font-size: 16px;
  line-height: 22px;
}

/* Primary Variant Customization */
.variant-primary:not(.is-disabled) {
  --n-color: var(--color-brand-500) !important;
  --n-color-hover: var(--color-brand-700) !important;
  --n-color-pressed: var(--color-brand-700) !important;
  --n-text-color: var(--color-surface-container-lowest) !important;
  --n-text-color-hover: var(--color-surface-container-lowest) !important;
  --n-text-color-pressed: var(--color-surface-container-lowest) !important;
  --n-border: 1px solid transparent !important;
  --n-border-hover: 1px solid transparent !important;
  --n-border-pressed: 1px solid transparent !important;
}

/* Secondary Variant Customization */
.variant-secondary:not(.is-disabled) {
  --n-color: var(--color-bg-surface) !important;
  --n-color-hover: var(--color-bg-subtle) !important;
  --n-color-pressed: var(--color-bg-subtle) !important;
  --n-text-color: var(--color-text-primary) !important;
  --n-text-color-hover: var(--color-text-primary) !important;
  --n-text-color-pressed: var(--color-text-primary) !important;
  --n-border: 1px solid var(--color-border) !important;
  --n-border-hover: 1px solid var(--color-border) !important;
  --n-border-pressed: 1px solid var(--color-border) !important;
}

/* Ghost Variant Customization */
.variant-ghost:not(.is-disabled) {
  --n-color: transparent !important;
  --n-color-hover: var(--color-bg-subtle) !important;
  --n-color-pressed: var(--color-bg-subtle) !important;
  --n-text-color: var(--color-text-primary) !important;
  --n-text-color-hover: var(--color-text-primary) !important;
  --n-text-color-pressed: var(--color-text-primary) !important;
}

/* Danger Variant Customization */
.variant-danger:not(.is-disabled) {
  --n-color: var(--color-danger-500) !important;
  --n-color-hover: var(--color-danger-600-exact) !important;
  --n-color-pressed: var(--color-danger-700-exact) !important;
  --n-text-color: var(--color-surface-container-lowest) !important;
  --n-text-color-hover: var(--color-surface-container-lowest) !important;
  --n-text-color-pressed: var(--color-surface-container-lowest) !important;
  --n-border: 1px solid transparent !important;
  --n-border-hover: 1px solid transparent !important;
  --n-border-pressed: 1px solid transparent !important;
}

/* Link Variant Customization */
.variant-link:not(.is-disabled) {
  --n-color: transparent !important;
  --n-color-hover: transparent !important;
  --n-color-pressed: transparent !important;
  --n-text-color: var(--color-brand-700) !important;
  --n-text-color-hover: var(--color-brand-700) !important;
  --n-text-color-pressed: var(--color-brand-700) !important;
}
.variant-link:not(.is-disabled):hover {
  text-decoration: underline;
}

/* Strict Disabled state according to specs (Solid color, no opacity) */
.is-disabled {
  opacity: 1 !important;
  cursor: not-allowed !important;
}

/* The NButton applies its disabled colors automatically when disabled="true", 
   but we strictly enforce it here as well */
:deep(.n-button.n-button--disabled) {
  background-color: var(--color-bg-subtle) !important;
  border-color: transparent !important;
  color: var(--color-text-disabled) !important;
  opacity: 1 !important;
}
.variant-link.is-disabled {
  background-color: transparent !important;
}

/* Focus Ring */
.base-button:focus-visible:not(.is-disabled) {
  outline: none;
  box-shadow: var(--shadow-focus) !important;
}

/* Spring scale animation */
.base-button:active:not(.is-disabled) {
  transform: scale(0.98);
  transition: transform var(--motion-duration-spring) var(--motion-ease-spring);
}
</style>
