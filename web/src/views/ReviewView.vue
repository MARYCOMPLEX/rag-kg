<script setup lang="ts">
import { storeToRefs } from 'pinia'
import AppIcon from '../components/base/AppIcon.vue'
import ReviewCitationsPanel from '../components/review/ReviewCitationsPanel.vue'
import ReviewDraftStream from '../components/review/ReviewDraftStream.vue'
import ReviewNoticeBar from '../components/review/ReviewNoticeBar.vue'
import ReviewPipelinePanel from '../components/review/ReviewPipelinePanel.vue'
import { useReviewStore } from '../stores/review'

const review = useReviewStore()
const {
  reviewRunning,
  draftTokens,
  selectedCitation,
  highlightedCitation,
  usesApiData,
} = storeToRefs(review)
</script>

<template>
  <section class="review-workspace">
    <div v-if="usesApiData" class="review-pending-state" role="status">
      <AppIcon name="review" :size="28" />
      <h1>Review contract pending</h1>
      <p>
        API mode hides seeded pipeline steps, draft prose, citation rows, run stats, and timer-driven progress until
        <code>/api/libraries/{libraryId}/reviews/current</code>,
        <code>/api/libraries/{libraryId}/reviews</code>, regeneration/cancel endpoints, and stream events are defined.
      </p>
    </div>

    <div v-else class="review-panel-layout">
      <ReviewPipelinePanel
        :steps="review.pipelineSteps"
        :stats="review.runStats"
        :running="reviewRunning"
        :draft-tokens="draftTokens"
        @cancel="review.cancelReview"
        @regenerate="review.regenerateSection"
      />

      <ReviewDraftStream
        :running="reviewRunning"
        :draft-tokens="draftTokens"
        @citation="review.activateCitation"
      />

      <ReviewCitationsPanel
        :citations="review.liveCitations"
        :selected-id="selectedCitation"
        :highlighted-id="highlightedCitation"
        @select="review.activateCitation"
      />
    </div>

    <ReviewNoticeBar v-if="!usesApiData" />
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

.review-panel-layout {
  display: flex;
  flex: 1 1 auto;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
}

.review-panel-layout :deep(.review-pipeline-panel) {
  flex-basis: clamp(280px, calc(40% - 128px), 320px);
}

.review-panel-layout :deep(.review-citations-panel) {
  flex-basis: clamp(300px, calc(60% - 312px), 360px);
}
</style>
