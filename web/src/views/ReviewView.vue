<script setup lang="ts">
import { storeToRefs } from 'pinia'
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
} = storeToRefs(review)
</script>

<template>
  <section class="review-workspace">
    <div class="review-panel-layout">
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

    <ReviewNoticeBar />
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
