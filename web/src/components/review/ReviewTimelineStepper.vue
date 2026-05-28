<script setup lang="ts">
import type { ReviewPipelineStep } from '../../domain/review/types'
import AppIcon from '../base/AppIcon.vue'

defineProps<{
  steps: ReviewPipelineStep[]
  draftTokens: number
  draftTokenLimit: number
}>()

const emit = defineEmits<{
  regenerate: [sectionId: string]
}>()
</script>

<template>
  <nav class="review-stepper" aria-label="Pipeline steps">
    <ol class="review-stepper-list">
      <li
        v-for="step in steps"
        :key="step.id"
        class="review-stepper-item"
        :class="`is-${step.status}`"
        :aria-current="step.status === 'active' ? 'step' : undefined"
      >
        <span class="stepper-marker" aria-hidden="true">
          <AppIcon v-if="step.status === 'done'" name="check" :size="13" />
          <span v-else-if="step.status === 'active'" class="active-step-dot" />
        </span>

        <span class="stepper-copy">
          <span class="stepper-title">{{ step.label }}</span>
          <button
            v-if="step.status !== 'pending'"
            class="regenerate-action"
            type="button"
            :aria-label="`Regenerate ${step.label}`"
            @click="emit('regenerate', step.id)"
          >
            <AppIcon name="refresh" :size="13" />
          </button>

          <span v-if="step.details" class="stepper-details">
            <span
              v-for="detail in step.details"
              :key="detail.label"
              class="stepper-detail"
              :class="`is-${detail.status}`"
            >
              <AppIcon :name="detail.status === 'done' ? 'check' : 'pencil'" :size="13" />
              <span>{{ detail.status === 'active' ? `Draft (${draftTokens}/${draftTokenLimit} tok)` : detail.label }}</span>
            </span>
          </span>
        </span>
      </li>
    </ol>
  </nav>
</template>

<style scoped>
.review-stepper {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  padding: 16px;
}

.review-stepper-list {
  position: relative;
  display: grid;
  gap: 24px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.review-stepper-list::before {
  position: absolute;
  top: 12px;
  bottom: 12px;
  left: 12px;
  width: 2px;
  transform: translateX(-50%);
  background: var(--color-surface-container-high);
  content: "";
}

.review-stepper-item {
  position: relative;
  display: grid;
  grid-template-columns: 24px minmax(0, 1fr);
  gap: 8px;
  color: var(--color-on-surface-variant);
}

.review-stepper-item.is-pending {
  opacity: .5;
}

.stepper-marker {
  position: relative;
  z-index: var(--z-raised);
  display: grid;
  place-items: center;
  width: 24px;
  height: 24px;
  border: 2px solid var(--color-outline-variant);
  border-radius: var(--radius-indicator);
  background: var(--color-surface);
  color: var(--color-citation);
}

.is-done .stepper-marker {
  border-color: transparent;
  background: var(--color-alpha-citation-10);
}

.is-active .stepper-marker {
  border-color: var(--color-primary);
}

.active-step-dot {
  width: 8px;
  height: 8px;
  border-radius: var(--radius-indicator);
  background: var(--color-primary);
  animation: review-pulse var(--motion-duration-blink) ease-in-out infinite;
}

.stepper-copy {
  position: relative;
  display: block;
  min-width: 0;
  padding-top: 1px;
}

.stepper-title {
  display: block;
  color: var(--color-on-surface);
  font-size: 14px;
  line-height: 22px;
}

.is-active .stepper-title {
  color: var(--color-primary);
  font-weight: 600;
}

.regenerate-action {
  position: absolute;
  top: 0;
  right: -4px;
  display: grid;
  place-items: center;
  width: 22px;
  height: 22px;
  border: 0;
  border-radius: var(--radius-control);
  background: var(--color-surface);
  color: var(--color-primary);
  opacity: 0;
  transform: translateX(4px);
  transition:
    opacity var(--motion-duration-normal) var(--motion-ease-standard),
    transform var(--motion-duration-normal) var(--motion-ease-standard),
    background var(--motion-duration-normal) var(--motion-ease-standard);
}

.review-stepper-item:hover .regenerate-action,
.regenerate-action:focus-visible {
  opacity: 1;
  transform: translateX(0);
}

.regenerate-action:hover {
  background: var(--color-primary-fixed);
}

.stepper-details {
  display: grid;
  gap: 4px;
  margin-top: 4px;
}

.stepper-detail {
  display: flex;
  align-items: center;
  gap: 4px;
  color: var(--color-on-surface-variant);
  font-family: "JetBrains Mono", monospace;
  font-size: 12px;
  line-height: 16px;
}

.stepper-detail.is-active {
  color: var(--color-primary);
}

@keyframes review-pulse {
  50% {
    opacity: .18;
  }
}
</style>
