<script setup lang="ts">
import { computed, nextTick, ref, useId, watch } from 'vue'
import AppIcon from './AppIcon.vue'

const props = withDefaults(defineProps<{
  show: boolean
  title?: string
  subtitle?: string
  size?: 'sm' | 'md' | 'lg' | 'command'
  role?: 'dialog' | 'alertdialog'
  dismissible?: boolean
  closeLabel?: string
  hideHeader?: boolean
}>(), {
  title: '',
  subtitle: '',
  size: 'md',
  role: 'dialog',
  dismissible: true,
  closeLabel: 'Close modal',
  hideHeader: false,
})

const emit = defineEmits<{
  (event: 'update:show', value: boolean): void
  (event: 'close'): void
}>()

const panelRef = ref<HTMLElement | null>(null)
const titleId = useId()
const subtitleId = useId()

const labelledBy = computed(() => props.title ? titleId : undefined)
const describedBy = computed(() => props.subtitle ? subtitleId : undefined)

function requestClose() {
  if (!props.dismissible)
    return

  emit('update:show', false)
  emit('close')
}

function focusInitialElement() {
  void nextTick(() => {
    const panel = panelRef.value
    if (!panel)
      return

    const target = panel.querySelector<HTMLElement>(
      '[data-autofocus], input:not([disabled]), textarea:not([disabled]), select:not([disabled]), button:not([disabled]), [tabindex]:not([tabindex="-1"])',
    )
    ;(target ?? panel).focus()
  })
}

watch(() => props.show, (next) => {
  if (next)
    focusInitialElement()
})
</script>

<template>
  <Teleport to="body">
    <Transition name="base-modal" appear>
      <section
        v-if="show"
        class="base-modal-layer"
        :class="[`base-modal-size-${size}`, { 'is-command': size === 'command' }]"
        @keydown.esc.stop.prevent="requestClose"
      >
        <button
          class="base-modal-scrim"
          type="button"
          aria-label="Close overlay"
          :disabled="!dismissible"
          @click="requestClose"
        />

        <article
          ref="panelRef"
          class="base-modal-panel"
          :role="role"
          aria-modal="true"
          :aria-labelledby="labelledBy"
          :aria-describedby="describedBy"
          tabindex="-1"
          @click.stop
        >
          <slot name="header">
            <header v-if="!hideHeader" class="base-modal-header">
              <div class="base-modal-heading">
                <slot name="icon" />
                <div>
                  <h2 v-if="title" :id="titleId">
                    {{ title }}
                  </h2>
                  <p v-if="subtitle" :id="subtitleId">
                    {{ subtitle }}
                  </p>
                </div>
              </div>
              <button
                v-if="dismissible"
                class="base-modal-close"
                type="button"
                :aria-label="closeLabel"
                @click="requestClose"
              >
                <AppIcon name="close" :size="18" />
              </button>
            </header>
          </slot>

          <div class="base-modal-body">
            <slot />
          </div>

          <footer v-if="$slots.footer" class="base-modal-footer">
            <slot name="footer" />
          </footer>
        </article>
      </section>
    </Transition>
  </Teleport>
</template>

<style scoped>
.base-modal-layer {
  position: fixed;
  inset: 0;
  z-index: var(--z-modal);
  display: grid;
  place-items: start center;
  padding: 12vh 24px 24px;
}

.base-modal-layer.is-command {
  z-index: var(--z-cmdk);
  padding-top: 18vh;
}

.base-modal-scrim {
  position: absolute;
  inset: 0;
  border: 0;
  background: var(--color-alpha-modal-scrim);
  backdrop-filter: blur(4px);
}

.base-modal-scrim:disabled {
  cursor: default;
}

.base-modal-panel {
  position: relative;
  display: flex;
  flex-direction: column;
  width: min(var(--base-modal-width), calc(100vw - 48px));
  max-height: min(var(--base-modal-max-height), calc(100vh - 96px));
  overflow: hidden;
  border: 1px solid var(--color-outline-variant);
  border-radius: var(--radius-modal);
  background: var(--color-surface);
  box-shadow: var(--shadow-modal);
  outline: none;
}

.base-modal-size-sm {
  --base-modal-width: 520px;
  --base-modal-max-height: 640px;
}

.base-modal-size-md {
  --base-modal-width: 600px;
  --base-modal-max-height: 720px;
}

.base-modal-size-lg {
  --base-modal-width: 720px;
  --base-modal-max-height: 760px;
}

.base-modal-size-command {
  --base-modal-width: 720px;
  --base-modal-max-height: 560px;
}

.base-modal-header,
.base-modal-footer {
  flex: 0 0 auto;
}

.base-modal-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 28px 32px 0;
}

.base-modal-heading {
  display: flex;
  min-width: 0;
  gap: 14px;
}

.base-modal-heading h2 {
  margin: 0;
  color: var(--color-on-surface);
  font-family: "Hanken Grotesk", Inter, sans-serif;
  font-size: 22px;
  font-weight: 700;
  letter-spacing: 0;
  line-height: 27px;
}

.base-modal-heading p {
  max-width: 54ch;
  margin: 6px 0 0;
  color: var(--color-on-surface-variant);
  font-size: 14px;
  line-height: 22px;
}

.base-modal-close {
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  flex: 0 0 auto;
  border: 1px solid var(--color-outline-variant);
  border-radius: var(--radius-control);
  background: var(--color-surface-container-lowest);
  color: var(--color-on-surface-variant);
  transition:
    background-color var(--motion-duration-fast) var(--motion-ease-standard),
    color var(--motion-duration-fast) var(--motion-ease-standard),
    box-shadow var(--motion-duration-fast) var(--motion-ease-standard);
}

.base-modal-close:hover {
  background: var(--color-surface-container-low);
  color: var(--color-on-surface);
}

.base-modal-close:focus-visible {
  box-shadow: var(--shadow-focus);
  outline: none;
}

.base-modal-body {
  flex: 1 1 auto;
  min-height: 0;
  overflow: auto;
  padding: 24px 32px;
}

.base-modal-footer {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
  border-top: 1px solid var(--color-outline-variant);
  background: var(--color-surface-container-low);
  padding: 16px 32px;
}

.base-modal-layer.is-command .base-modal-body {
  display: flex;
  overflow: hidden;
  min-height: 0;
  flex-direction: column;
  padding: 0;
}

.base-modal-layer.is-command .base-modal-footer {
  justify-content: flex-start;
  min-height: 40px;
  gap: 20px;
  padding-top: 10px;
  padding-bottom: 10px;
}

.base-modal-enter-active,
.base-modal-leave-active {
  transition: opacity var(--motion-duration-modal) var(--motion-ease-emphasized);
}

.base-modal-enter-active .base-modal-panel,
.base-modal-leave-active .base-modal-panel {
  transition:
    opacity var(--motion-duration-modal) var(--motion-ease-emphasized),
    transform var(--motion-duration-modal) var(--motion-ease-emphasized);
}

.base-modal-enter-from,
.base-modal-leave-to {
  opacity: 0;
}

.base-modal-enter-from .base-modal-panel,
.base-modal-leave-to .base-modal-panel {
  opacity: 0;
  transform: translateY(8px) scale(.96);
}

@media (max-width: 700px) {
  .base-modal-layer,
  .base-modal-layer.is-command {
    align-items: end;
    padding: 16px;
  }

  .base-modal-panel {
    width: 100%;
    max-height: calc(100vh - 32px);
  }

  .base-modal-header,
  .base-modal-body,
  .base-modal-footer {
    padding-right: 20px;
    padding-left: 20px;
  }
}
</style>
