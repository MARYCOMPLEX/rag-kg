<script setup lang="ts">
import { ref } from 'vue'
import type { ReviewPipelineStep, ReviewRunStat } from '../../types/application'
import AppIcon from '../base/AppIcon.vue'
import ReviewTimelineStepper from './ReviewTimelineStepper.vue'

defineProps<{
  steps: ReviewPipelineStep[]
  stats: ReviewRunStat[]
  running: boolean
  draftTokens: number
}>()

const emit = defineEmits<{
  cancel: []
  regenerate: [label: string]
}>()

const cancelPending = ref(false)

function confirmCancel() {
  cancelPending.value = false
  emit('cancel')
}
</script>

<template>
  <aside class="review-pipeline-panel" aria-label="Review pipeline">
    <header class="review-panel-heading">
      <h2>Pipeline</h2>
    </header>

    <ReviewTimelineStepper :steps="steps" :draft-tokens="draftTokens" @regenerate="emit('regenerate', $event)" />

    <footer class="run-stats-panel">
      <h3>Run Stats</h3>
      <dl class="review-run-stats">
        <div v-for="stat in stats" :key="stat.label">
          <dt>{{ stat.label }}</dt>
          <dd :class="{ accent: stat.accent }">
            {{ stat.value }}
          </dd>
        </div>
      </dl>
      <div class="run-actions">
        <button class="cancel-run-button" type="button" :disabled="!running" @click="cancelPending = true">
          Cancel run
        </button>
        <button class="download-draft-button" type="button" :disabled="running">
          <AppIcon name="download" :size="14" />
          Download draft .md
        </button>
      </div>
      <Transition name="confirm">
        <div v-if="cancelPending && running" class="cancel-confirmation" role="alertdialog" aria-label="Cancel review run?">
          <span>Keep generated sections?</span>
          <div>
            <button type="button" @click="cancelPending = false">
              Keep running
            </button>
            <button type="button" class="danger" @click="confirmCancel">
              Cancel
            </button>
          </div>
        </div>
      </Transition>
    </footer>
  </aside>
</template>

<style scoped>
.review-pipeline-panel {
  display: flex;
  flex: 0 0 320px;
  flex-direction: column;
  min-height: 0;
  border-right: 1px solid var(--color-outline-variant);
  background: var(--color-surface);
}

.review-panel-heading {
  flex: 0 0 auto;
  border-bottom: 1px solid var(--color-outline-variant);
  padding: 16px;
}

.review-panel-heading h2,
.run-stats-panel h3 {
  margin: 0;
  color: var(--color-on-surface-variant);
  font-family: Inter, sans-serif;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0;
  line-height: 16px;
  text-transform: uppercase;
}

.run-stats-panel {
  position: relative;
  flex: 0 0 auto;
  border-top: 1px solid var(--color-outline-variant);
  background: var(--color-surface-bright);
  padding: 16px;
}

.review-run-stats {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  margin: 8px 0 16px;
}

.review-run-stats dt {
  color: var(--color-on-surface-variant);
  font-family: "JetBrains Mono", monospace;
  font-size: 12px;
  line-height: 16px;
}

.review-run-stats dd {
  margin: 4px 0 0;
  color: var(--color-on-surface);
  font-size: 13px;
  font-weight: 600;
  line-height: 20px;
}

.review-run-stats dd.accent {
  color: var(--color-primary);
}

.run-actions {
  display: grid;
  gap: 8px;
}

.cancel-run-button,
.download-draft-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 32px;
  gap: 6px;
  border-radius: var(--radius-control);
  font-size: 13px;
  line-height: 20px;
  transition:
    background var(--motion-duration-normal) var(--motion-ease-standard),
    border-color var(--motion-duration-normal) var(--motion-ease-standard),
    color var(--motion-duration-normal) var(--motion-ease-standard);
}

.cancel-run-button {
  border: 1px solid var(--color-primary);
  background: var(--color-surface);
  color: var(--color-primary);
}

.cancel-run-button:hover:not(:disabled) {
  background: var(--color-primary-fixed);
}

.download-draft-button {
  border: 1px solid var(--color-outline-variant);
  background: var(--color-surface-container-low);
  color: var(--color-outline);
}

.cancel-run-button:disabled,
.download-draft-button:disabled {
  cursor: not-allowed;
}

.cancel-confirmation {
  position: absolute;
  right: 12px;
  bottom: 102px;
  left: 12px;
  display: grid;
  gap: 10px;
  border: 1px solid var(--color-outline-variant);
  border-radius: var(--radius-popover);
  background: var(--color-surface-container-lowest);
  padding: 12px;
  box-shadow: var(--shadow-lg);
  color: var(--color-on-surface);
  font-size: 13px;
}

.cancel-confirmation div {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.cancel-confirmation button {
  height: 28px;
  border: 1px solid var(--color-outline-variant);
  border-radius: var(--radius-control);
  background: var(--color-surface-container-lowest);
  padding: 0 10px;
  color: var(--color-on-surface-variant);
}

.cancel-confirmation button.danger {
  border-color: var(--color-error);
  color: var(--color-error);
}

.confirm-enter-active,
.confirm-leave-active {
  transition:
    opacity var(--motion-duration-fast) var(--motion-ease-standard),
    transform var(--motion-duration-fast) var(--motion-ease-standard);
}

.confirm-enter-from,
.confirm-leave-to {
  opacity: 0;
  transform: translateY(4px);
}

</style>
