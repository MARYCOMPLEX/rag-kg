<script setup lang="ts">
import { computed, ref } from 'vue'
import { onClickOutside } from '@vueuse/core'
import AppIcon from './AppIcon.vue'

interface RichDropdownOption {
  value: string
  label: string
  meta?: string
  disabled?: boolean
}

const props = withDefaults(defineProps<{
  modelValue?: string
  options: RichDropdownOption[]
  placeholder?: string
  ariaLabel?: string
  align?: 'start' | 'end'
  disabled?: boolean
}>(), {
  align: 'start',
  placeholder: 'Select',
  ariaLabel: 'Select option',
})

const emit = defineEmits<{
  'update:modelValue': [value: string]
  select: [option: RichDropdownOption]
}>()

const rootRef = ref<HTMLElement | null>(null)
const open = ref(false)

const selectedOption = computed(() => {
  return props.options.find(option => option.value === props.modelValue)
})

const triggerLabel = computed(() => selectedOption.value?.label ?? props.placeholder)

onClickOutside(rootRef, () => {
  open.value = false
})

function toggleDropdown() {
  if (props.disabled)
    return

  open.value = !open.value
}

function closeDropdown() {
  open.value = false
}

function selectOption(option: RichDropdownOption) {
  if (option.disabled)
    return

  emit('update:modelValue', option.value)
  emit('select', option)
  closeDropdown()
}

function onTriggerKeydown(event: KeyboardEvent) {
  if (['Enter', ' ', 'ArrowDown'].includes(event.key)) {
    event.preventDefault()
    open.value = true
    return
  }

  if (event.key === 'Escape')
    closeDropdown()
}
</script>

<template>
  <div
    ref="rootRef"
    class="rich-dropdown"
    :class="[`align-${align}`, { 'is-open': open, 'is-disabled': disabled }]"
  >
    <button
      class="rich-dropdown-trigger"
      type="button"
      :aria-label="ariaLabel"
      :aria-expanded="open"
      :disabled="disabled"
      aria-haspopup="listbox"
      @click.stop="toggleDropdown"
      @keydown="onTriggerKeydown"
    >
      <span v-if="$slots['trigger-icon']" class="rich-dropdown-trigger-icon" aria-hidden="true">
        <slot name="trigger-icon" :option="selectedOption" />
      </span>
      <span class="rich-dropdown-trigger-label">{{ triggerLabel }}</span>
      <AppIcon class="rich-dropdown-chevron" name="chevron" :size="18" />
    </button>

    <Transition name="rich-dropdown">
      <div v-if="open" class="rich-dropdown-panel" @click.stop @keydown.esc.stop.prevent="closeDropdown">
        <div class="rich-dropdown-options" role="listbox" :aria-label="ariaLabel">
          <button
            v-for="option in options"
            :key="option.value"
            class="rich-dropdown-option"
            :class="{ 'is-selected': option.value === modelValue }"
            type="button"
            role="option"
            :aria-selected="option.value === modelValue"
            :disabled="option.disabled"
            @click="selectOption(option)"
          >
            <span class="rich-dropdown-option-main">
              <span v-if="$slots['option-icon']" class="rich-dropdown-option-icon" aria-hidden="true">
                <slot name="option-icon" :option="option" :selected="option.value === modelValue" />
              </span>
              <span class="rich-dropdown-option-label">{{ option.label }}</span>
            </span>
            <span v-if="option.meta" class="rich-dropdown-option-meta">{{ option.meta }}</span>
          </button>
        </div>

        <div v-if="$slots.action" class="rich-dropdown-action">
          <slot name="action" :close="closeDropdown" />
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.rich-dropdown {
  --rich-dropdown-width: 260px;
  --rich-dropdown-panel-width: 100%;
  --rich-dropdown-trigger-height: 40px;
  --rich-dropdown-radius: var(--radius-popover);
  --rich-dropdown-panel-radius: var(--rich-dropdown-radius);
  --rich-dropdown-font-size: 16px;

  position: relative;
  display: inline-flex;
  width: var(--rich-dropdown-width);
  min-width: 0;
}

.rich-dropdown.align-end .rich-dropdown-panel {
  right: 0;
  left: auto;
}

.rich-dropdown-trigger {
  box-sizing: border-box;
  display: inline-flex;
  align-items: center;
  width: 100%;
  height: var(--rich-dropdown-trigger-height);
  min-width: 0;
  gap: 14px;
  border: 1px solid var(--color-outline-variant);
  border-radius: var(--rich-dropdown-radius);
  background: var(--color-surface-container-lowest);
  padding: 0 14px;
  color: var(--color-on-surface);
  font-size: var(--rich-dropdown-font-size);
  font-weight: 700;
  line-height: 22px;
  box-shadow: var(--shadow-xs);
  transition:
    border-color var(--motion-duration-normal) var(--motion-ease-standard),
    box-shadow var(--motion-duration-normal) var(--motion-ease-standard),
    background var(--motion-duration-normal) var(--motion-ease-standard);
}

.rich-dropdown-trigger:hover {
  border-color: var(--color-alpha-primary-container-68);
  background: var(--color-surface-container-lowest);
}

.rich-dropdown-trigger:focus-visible,
.rich-dropdown.is-open .rich-dropdown-trigger {
  border-color: var(--color-primary-container);
  box-shadow: var(--shadow-dropdown-trigger-focus);
  outline: none;
}

.rich-dropdown.is-disabled {
  opacity: .56;
  pointer-events: none;
}

.rich-dropdown-trigger-icon {
  display: inline-grid;
  flex: 0 0 auto;
  place-items: center;
}

.rich-dropdown-trigger-label {
  flex: 1 1 auto;
  min-width: 0;
  overflow: hidden;
  line-height: 22px;
  text-align: left;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.rich-dropdown-chevron {
  flex: 0 0 auto;
  color: var(--color-outline);
  transition: transform var(--motion-duration-normal) var(--motion-ease-standard);
}

.rich-dropdown.is-open .rich-dropdown-chevron {
  transform: rotate(180deg);
}

.rich-dropdown-panel {
  box-sizing: border-box;
  position: absolute;
  top: calc(100% + 10px);
  left: 0;
  z-index: var(--z-dropdown);
  width: var(--rich-dropdown-panel-width);
  min-width: 0;
  overflow: hidden;
  border: 1px solid var(--color-alpha-outline-variant-72);
  border-radius: var(--rich-dropdown-panel-radius);
  background: var(--color-surface-container-lowest);
  box-shadow: var(--shadow-dropdown);
}

.rich-dropdown-options {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 12px;
}

.rich-dropdown-option {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 52px;
  gap: 18px;
  border: 0;
  border-radius: var(--radius-control);
  background: transparent;
  padding: 0 18px;
  color: var(--color-on-surface);
  text-align: left;
  transition:
    background var(--motion-duration-normal) var(--motion-ease-standard),
    color var(--motion-duration-normal) var(--motion-ease-standard);
}

.rich-dropdown-option:hover,
.rich-dropdown-option:focus-visible {
  background: var(--color-surface-container-high);
  outline: none;
}

.rich-dropdown-option.is-selected {
  background: linear-gradient(90deg, var(--color-alpha-primary-10), var(--color-alpha-primary-6));
}

.rich-dropdown-option-main {
  display: inline-flex;
  align-items: center;
  min-width: 0;
  gap: 16px;
}

.rich-dropdown-option-icon {
  display: inline-grid;
  flex: 0 0 auto;
  place-items: center;
}

.rich-dropdown-option-label {
  min-width: 0;
  overflow: hidden;
  font-size: 15px;
  font-weight: 800;
  letter-spacing: 0;
  line-height: 22px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.rich-dropdown-option-meta {
  flex: 0 0 auto;
  color: var(--color-outline);
  font-size: 14px;
  font-weight: 600;
  letter-spacing: .04em;
  line-height: 20px;
  white-space: nowrap;
}

.rich-dropdown-action {
  border-top: 1px solid var(--color-outline-variant);
  padding: 10px 12px 12px;
}

.rich-dropdown-enter-active,
.rich-dropdown-leave-active {
  transition:
    opacity var(--motion-duration-fast) var(--motion-ease-standard),
    transform var(--motion-duration-fast) var(--motion-ease-standard);
}

.rich-dropdown-enter-from,
.rich-dropdown-leave-to {
  opacity: 0;
  transform: translateY(-4px) scale(.98);
}
</style>
