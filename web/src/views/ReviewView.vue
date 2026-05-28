<script setup lang="ts">
import { computed, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useRoute } from 'vue-router'
import AppIcon from '../components/base/AppIcon.vue'
import ReviewCitationsPanel from '../components/review/ReviewCitationsPanel.vue'
import ReviewDraftStream from '../components/review/ReviewDraftStream.vue'
import ReviewNoticeBar from '../components/review/ReviewNoticeBar.vue'
import ReviewPipelinePanel from '../components/review/ReviewPipelinePanel.vue'
import { useReviewStore } from '../stores/review'

const route = useRoute()
const review = useReviewStore()
const {
  currentRun,
  draftContent,
  draftTokens,
  highlightedCitation,
  liveCitations,
  pipelineSteps,
  reviewBackgrounded,
  reviewError,
  reviewRunning,
  reviewState,
  runStats,
  selectedCitation,
  usesApiData,
} = storeToRefs(review)
const libraryId = computed(() => String(route.params.libraryId ?? ''))
const showApiLoading = computed(() => usesApiData.value && reviewState.value === 'loading')
const showApiError = computed(() => usesApiData.value && reviewState.value === 'error')
const showApiEmpty = computed(() => usesApiData.value && reviewState.value === 'success' && !currentRun.value)

watch(libraryId, (nextLibraryId) => {
  if (nextLibraryId)
    void review.loadReview(nextLibraryId)
}, { immediate: true })

function startReview() {
  void review.createReview()
}

function reloadReview() {
  void review.loadReview(libraryId.value, true)
}

function regenerateSection(sectionId: string) {
  void review.regenerateSection(sectionId)
}
</script>

<template>
  <section class="review-workspace">
    <div v-if="showApiLoading" class="review-pending-state" role="status">
      <AppIcon name="review" :size="28" />
      <h1>Loading review</h1>
      <p>Fetching current run state, pipeline steps, draft content, citations, and run stats from the API.</p>
    </div>

    <div v-else-if="showApiError" class="review-pending-state is-error" role="alert">
      <AppIcon name="warning" :size="28" />
      <h1>Unable to load review</h1>
      <p>{{ reviewError }}</p>
      <button type="button" @click="reloadReview">
        Retry
      </button>
    </div>

    <div v-else-if="showApiEmpty" class="review-pending-state" role="status">
      <AppIcon name="review" :size="28" />
      <h1>No active review run</h1>
      <p>The backend returned no active review for this library.</p>
      <button type="button" @click="startReview">
        Start review
      </button>
    </div>

    <div v-else class="review-panel-stack">
      <div v-if="usesApiData && reviewError && currentRun" class="review-inline-error" role="alert">
        <AppIcon name="warning" :size="16" />
        <span>{{ reviewError }}</span>
        <button type="button" @click="reloadReview">
          Retry
        </button>
      </div>

      <div class="review-panel-layout">
        <ReviewPipelinePanel
          :steps="pipelineSteps"
          :stats="runStats"
          :running="reviewRunning"
          :draft-tokens="draftTokens"
          :draft-token-limit="draftContent?.draftTokenLimit ?? 0"
          @cancel="review.cancelReview"
          @regenerate="regenerateSection"
        />

        <ReviewDraftStream
          v-if="draftContent"
          :draft="draftContent"
          :running="reviewRunning"
          :draft-tokens="draftTokens"
          @citation="review.activateCitation"
        />

        <ReviewCitationsPanel
          :citations="liveCitations"
          :selected-id="selectedCitation"
          :highlighted-id="highlightedCitation"
          @select="review.activateCitation"
        />
      </div>
    </div>

    <ReviewNoticeBar v-if="!usesApiData" />
    <div v-else-if="reviewBackgrounded" class="review-background-note" role="status">
      <AppIcon name="info" :size="15" />
      <span>Review is running in the background.</span>
    </div>
  </section>
</template>

<style scoped>
.review-workspace {
  display: flex;
  flex-direction: column;
  width: 100%;
  height: 100%;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  background: var(--color-surface-container-low);
}

.review-pending-state {
  display: grid;
  flex: 1 1 auto;
  place-items: center;
  align-content: center;
  gap: 12px;
  margin: 24px;
  border: 1px dashed var(--color-outline-variant);
  border-radius: var(--radius-card);
  background: var(--color-surface);
  padding: 32px;
  color: var(--color-on-surface-variant);
  text-align: center;
}

.review-pending-state :deep(.app-icon) {
  color: var(--color-primary);
}

.review-pending-state h1 {
  margin: 0;
  color: var(--color-on-surface);
  font-size: 20px;
  line-height: 28px;
}

.review-pending-state p {
  max-width: 720px;
  margin: 0;
  line-height: 22px;
}

.review-pending-state code {
  color: var(--color-on-surface);
  font-size: .92em;
}

.review-pending-state.is-error :deep(.app-icon),
.review-pending-state.is-error h1 {
  color: var(--color-error);
}

.review-pending-state button {
  height: 34px;
  border: 1px solid var(--color-outline-variant);
  border-radius: var(--radius-control);
  background: var(--color-surface-container-lowest);
  padding: 0 14px;
  color: var(--color-primary);
  font-size: 13px;
  font-weight: 700;
}

.review-panel-layout {
  position: relative;
  display: flex;
  flex: 1 1 auto;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
}

.review-panel-stack {
  display: flex;
  flex: 1 1 auto;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
}

.review-inline-error {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 24px 24px 0;
  border: 1px solid var(--color-alpha-danger-20);
  border-radius: var(--radius-control);
  background: var(--color-error-container);
  padding: 10px 12px;
  color: var(--color-error);
  font-size: 13px;
  line-height: 18px;
}

.review-inline-error :deep(.app-icon) {
  flex: 0 0 auto;
}

.review-inline-error span {
  min-width: 0;
  flex: 1 1 auto;
}

.review-inline-error button {
  height: 28px;
  border: 1px solid var(--color-error);
  border-radius: var(--radius-control);
  background: var(--color-surface-container-lowest);
  padding: 0 10px;
  color: var(--color-error);
  font-size: 12px;
  font-weight: 700;
}

.review-panel-layout :deep(.review-pipeline-panel) {
  flex-basis: clamp(280px, calc(40% - 128px), 320px);
}

.review-panel-layout :deep(.review-citations-panel) {
  flex-basis: clamp(300px, calc(60% - 312px), 360px);
}

.review-background-note {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border-top: 1px solid var(--color-outline-variant);
  background: var(--color-surface-container-high);
  padding: 8px 16px;
  color: var(--color-on-surface-variant);
  font-size: 12px;
  line-height: 16px;
}

.review-background-note :deep(.app-icon) {
  color: var(--color-primary);
}
</style>
