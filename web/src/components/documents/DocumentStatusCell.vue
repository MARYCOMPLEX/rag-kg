<script setup lang="ts">
import { computed, useId } from 'vue'
import AppIcon from '../base/AppIcon.vue'
import type { DocumentStatus } from '../../domain/documents/types'

const props = withDefaults(defineProps<{
  documentId: string
  status: DocumentStatus
  open: boolean
}>(), {
  open: false,
})

const emit = defineEmits<{
  (event: 'toggle', documentId: string): void
  (event: 'close'): void
  (event: 'action'): void
}>()

const titleId = useId()
const popoverId = computed(() => `document-status-${props.documentId}-popover`)
const hasProgress = computed(() => typeof props.status.progress === 'number')
const progressWidth = computed(() => `${Math.min(100, Math.max(0, props.status.progress ?? 0))}%`)

function togglePopover() {
  emit('toggle', props.documentId)
}
</script>

<template>
  <td class="document-status-cell" :class="`is-${status.kind}`" @click.stop="togglePopover" @keydown.esc.stop.prevent="emit('close')">
    <button
      class="document-status-trigger"
      type="button"
      :aria-controls="popoverId"
      :aria-expanded="open"
      aria-haspopup="dialog"
      @click.stop="togglePopover"
    >
      <span v-if="hasProgress" class="progress-status">
        <span>{{ status.label }}</span>
        <b>{{ status.progressText || `${status.progress}%` }}</b>
        <i><em :style="{ width: progressWidth }" /></i>
      </span>
      <span v-else class="status" :class="status.kind">
        <i v-if="status.kind === 'ready'" />
        {{ status.label }}
      </span>
    </button>

    <button v-if="status.actionLabel" class="document-status-inline-action" type="button" @click.stop="emit('action')">
      {{ status.actionLabel }}
    </button>

    <div
      v-if="open"
      :id="popoverId"
      class="document-status-popover"
      :class="`is-${status.kind}`"
      role="dialog"
      aria-modal="false"
      :aria-labelledby="titleId"
      @click.stop
    >
      <div class="document-status-popover-head">
        <strong :id="titleId">{{ status.title }}</strong>
        <button type="button" :aria-label="`Close ${status.title}`" @click.stop="emit('close')">
          <AppIcon name="close" :size="14" />
        </button>
      </div>
      <code v-if="status.kind === 'failed'">{{ status.message }}</code>
      <p v-else>{{ status.message }}</p>
      <small>{{ status.meta }}</small>
      <button v-if="status.actionLabel" class="primary-btn" type="button" @click.stop="emit('action')">
        {{ status.actionLabel }}
      </button>
    </div>
  </td>
</template>

<style scoped>
.document-status-cell {
  position: relative;
  cursor: pointer;
}

.document-status-trigger,
.document-status-inline-action {
  border: 0;
  background: transparent;
}

.document-status-trigger {
  padding: 0;
  color: inherit;
  text-align: left;
  vertical-align: middle;
}

.document-status-trigger:focus-visible,
.document-status-inline-action:focus-visible,
.document-status-popover button:focus-visible {
  box-shadow: var(--shadow-focus);
  outline: none;
}

.document-status-inline-action {
  margin-left: 8px;
  color: var(--color-primary);
  font-family: "JetBrains Mono", monospace;
  font-size: 11px;
}

.progress-status {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  width: 140px;
  color: var(--color-warning);
  font-family: "JetBrains Mono", monospace;
  font-size: 11px;
}

.progress-status i {
  grid-column: 1 / 3;
  height: 4px;
  margin-top: 4px;
  border-radius: var(--radius-pill);
  background: var(--color-surface-container);
  overflow: hidden;
}

.progress-status em {
  display: block;
  height: 100%;
  background: currentColor;
}

.document-status-popover {
  position: fixed;
  z-index: var(--z-popover);
  bottom: 86px;
  right: 32px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: min(340px, calc(100vw - 48px));
  border: 1px solid var(--color-outline-variant);
  border-radius: var(--radius-popover);
  background: var(--color-surface-container-lowest);
  padding: 12px;
  box-shadow: var(--shadow-failure-popover);
  color: var(--color-on-surface);
  pointer-events: none;
  text-align: left;
}

.document-status-popover-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: var(--color-primary);
}

.document-status-popover.is-ready .document-status-popover-head {
  color: var(--color-success-700-exact);
}

.document-status-popover.is-indexing .document-status-popover-head,
.document-status-popover.is-parsing .document-status-popover-head {
  color: var(--color-warning-700-exact);
}

.document-status-popover.is-failed .document-status-popover-head {
  color: var(--color-error);
}

.document-status-popover-head button {
  display: inline-grid;
  place-items: center;
  width: 24px;
  height: 24px;
  border: 0;
  border-radius: var(--radius-control);
  background: transparent;
  color: var(--color-outline);
}

.document-status-popover button {
  pointer-events: auto;
}

.document-status-popover p,
.document-status-popover code,
.document-status-popover small {
  margin: 0;
  font-size: 10px;
}

.document-status-popover p {
  border: 1px solid var(--color-outline-variant);
  border-radius: var(--radius-card);
  background: var(--color-surface-container-low);
  padding: 8px;
  color: var(--color-on-surface-variant);
  line-height: 16px;
}

.document-status-popover code {
  border: 1px solid var(--color-alpha-danger-20);
  border-radius: var(--radius-card);
  background: var(--color-error-container);
  padding: 8px;
  color: var(--color-error);
  font-family: "JetBrains Mono", monospace;
  white-space: normal;
}

.document-status-popover small {
  color: var(--color-on-surface-variant);
  font-family: "JetBrains Mono", monospace;
}

.document-status-popover .primary-btn {
  align-self: flex-end;
  height: 28px;
  font-size: 11px;
}
</style>
