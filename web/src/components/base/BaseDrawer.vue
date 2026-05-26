<script setup lang="ts">
import { computed, nextTick, ref, useId, watch } from 'vue'
import AppIcon from './AppIcon.vue'

const props = withDefaults(defineProps<{
  show: boolean
  title?: string
  subtitle?: string
  size?: 'entity' | 'document' | 'wide'
  pinned?: boolean
  modal?: boolean
  dismissible?: boolean
  closeLabel?: string
}>(), {
  title: '',
  subtitle: '',
  size: 'document',
  pinned: false,
  modal: true,
  dismissible: false,
  closeLabel: 'Close drawer',
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
const ariaModal = computed<'true' | 'false'>(() => props.modal && !props.pinned ? 'true' : 'false')
const showScrim = computed(() => props.modal && !props.pinned)

function requestClose() {
  emit('update:show', false)
  emit('close')
}

function requestScrimClose() {
  if (props.dismissible)
    requestClose()
}

function focusInitialElement() {
  void nextTick(() => {
    const panel = panelRef.value
    if (!panel)
      return

    const target = panel.querySelector<HTMLElement>(
      '[data-autofocus], button:not([disabled]), input:not([disabled]), textarea:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])',
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
    <Transition name="base-drawer" appear>
      <section
        v-if="show"
        class="base-drawer-layer"
        :class="[{ pinned }, `base-drawer-size-${size}`]"
        @keydown.esc.stop.prevent="requestClose"
      >
        <button
          v-if="showScrim"
          class="base-drawer-scrim"
          type="button"
          aria-label="Dismiss drawer overlay"
          :disabled="!dismissible"
          @click="requestScrimClose"
        />

        <aside
          ref="panelRef"
          class="base-drawer-panel"
          role="dialog"
          :aria-modal="ariaModal"
          :aria-labelledby="labelledBy"
          :aria-describedby="describedBy"
          tabindex="-1"
          @click.stop
        >
          <header class="base-drawer-header">
            <div class="base-drawer-heading">
              <slot name="eyebrow" />
              <h2 v-if="title" :id="titleId">
                {{ title }}
              </h2>
              <p v-if="subtitle" :id="subtitleId">
                {{ subtitle }}
              </p>
            </div>
            <div class="base-drawer-actions">
              <slot name="actions" />
              <button class="base-drawer-close" type="button" :aria-label="closeLabel" @click="requestClose">
                <AppIcon name="close" :size="18" />
              </button>
            </div>
          </header>

          <div class="base-drawer-body">
            <slot />
          </div>

          <footer v-if="$slots.footer" class="base-drawer-footer">
            <slot name="footer" />
          </footer>
        </aside>
      </section>
    </Transition>
  </Teleport>
</template>

<style scoped>
.base-drawer-layer {
  position: fixed;
  inset: 0;
  z-index: var(--z-drawer);
  display: flex;
  justify-content: flex-end;
  pointer-events: none;
}

.base-drawer-scrim {
  position: absolute;
  inset: 0;
  border: 0;
  background: var(--color-alpha-drawer-scrim);
  pointer-events: auto;
}

.base-drawer-scrim:disabled {
  cursor: default;
}

.base-drawer-panel {
  position: relative;
  display: flex;
  flex: 0 0 min(var(--base-drawer-width), 100vw);
  flex-direction: column;
  width: min(var(--base-drawer-width), 100vw);
  height: 100vh;
  border-left: 1px solid var(--color-outline-variant);
  border-radius: var(--radius-drawer);
  background: var(--color-surface);
  box-shadow: var(--shadow-side-drawer);
  outline: none;
  pointer-events: auto;
}

.base-drawer-layer.pinned .base-drawer-panel {
  box-shadow: var(--shadow-side-drawer-subtle);
}

.base-drawer-size-entity {
  --base-drawer-width: 380px;
}

.base-drawer-size-document {
  --base-drawer-width: 800px;
}

.base-drawer-size-wide {
  --base-drawer-width: 920px;
}

.base-drawer-header,
.base-drawer-footer {
  flex: 0 0 auto;
}

.base-drawer-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
  border-bottom: 1px solid var(--color-outline-variant);
  padding: 24px 32px 20px;
}

.base-drawer-heading {
  min-width: 0;
}

.base-drawer-heading h2 {
  display: -webkit-box;
  overflow: hidden;
  margin: 8px 0 6px;
  color: var(--color-on-surface);
  font-family: "Hanken Grotesk", Inter, sans-serif;
  font-size: 22px;
  font-weight: 700;
  letter-spacing: 0;
  line-height: 27px;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.base-drawer-heading p {
  overflow: hidden;
  margin: 0;
  color: var(--color-on-surface-variant);
  font-size: 14px;
  line-height: 22px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.base-drawer-actions {
  display: flex;
  align-items: center;
  flex: 0 0 auto;
  gap: 8px;
}

.base-drawer-close,
.base-drawer-actions :deep(button) {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 32px;
  height: 32px;
  border: 1px solid var(--color-outline-variant);
  border-radius: var(--radius-control);
  background: var(--color-surface-container-lowest);
  color: var(--color-on-surface-variant);
  transition:
    background-color var(--motion-duration-fast) var(--motion-ease-standard),
    color var(--motion-duration-fast) var(--motion-ease-standard),
    box-shadow var(--motion-duration-fast) var(--motion-ease-standard);
}

.base-drawer-actions :deep(button) {
  gap: 6px;
  padding: 0 10px;
  font-size: 13px;
  font-weight: 500;
}

.base-drawer-close:hover,
.base-drawer-actions :deep(button:hover) {
  background: var(--color-surface-container-low);
  color: var(--color-on-surface);
}

.base-drawer-close:focus-visible,
.base-drawer-actions :deep(button:focus-visible) {
  box-shadow: var(--shadow-focus);
  outline: none;
}

.base-drawer-body {
  flex: 1 1 auto;
  min-height: 0;
  overflow: auto;
  padding: 24px 32px;
}

.base-drawer-footer {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
  border-top: 1px solid var(--color-outline-variant);
  background: var(--color-surface-container-low);
  padding: 16px 32px;
}

.base-drawer-enter-active,
.base-drawer-leave-active {
  transition: opacity var(--motion-duration-modal) var(--motion-ease-emphasized);
}

.base-drawer-enter-active .base-drawer-panel,
.base-drawer-leave-active .base-drawer-panel {
  transition: transform var(--motion-duration-modal) var(--motion-ease-emphasized);
}

.base-drawer-enter-from,
.base-drawer-leave-to {
  opacity: 0;
}

.base-drawer-enter-from .base-drawer-panel,
.base-drawer-leave-to .base-drawer-panel {
  transform: translateX(100%);
}

@media (max-width: 900px) {
  .base-drawer-panel {
    flex-basis: 100vw;
    width: 100vw;
    border-radius: var(--radius-drawer);
  }

  .base-drawer-header,
  .base-drawer-body,
  .base-drawer-footer {
    padding-right: 20px;
    padding-left: 20px;
  }
}
</style>
