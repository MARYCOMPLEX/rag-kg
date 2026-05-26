import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { reviewCitations, reviewPipelineSteps, reviewRunStats } from '../mocks/review'
import { useUiStore } from './ui'

export const useReviewStore = defineStore('review', () => {
  const reviewRunning = ref(true)
  const reviewBackgrounded = ref(false)
  const reviewProgress = ref(47)
  const taskTick = ref(0)
  const draftTokens = ref(324)
  const selectedCitation = ref('5')
  const highlightedCitation = ref('5')

  const pipelineSteps = computed(() => reviewPipelineSteps)
  const liveCitations = computed(() => reviewCitations)
  const runStats = computed(() => reviewRunStats)

  let taskTimer: number | null = null
  let citationHighlightTimer: number | null = null

  function startTaskRuntime() {
    if (taskTimer)
      return

    taskTimer = window.setInterval(() => {
      taskTick.value += 1
      if (reviewRunning.value && reviewProgress.value < 96) {
        reviewProgress.value += 1
        draftTokens.value = Math.min(draftTokens.value + 8, 800)
      }
    }, 2600)
  }

  function stopTaskRuntime() {
    if (taskTimer)
      window.clearInterval(taskTimer)
    taskTimer = null
    if (citationHighlightTimer)
      window.clearTimeout(citationHighlightTimer)
    citationHighlightTimer = null
  }

  function activateCitation(id: string) {
    selectedCitation.value = id
    highlightedCitation.value = id

    if (citationHighlightTimer)
      window.clearTimeout(citationHighlightTimer)

    citationHighlightTimer = window.setTimeout(() => {
      highlightedCitation.value = ''
    }, 800)
  }

  function regenerateSection(label: string) {
    const ui = useUiStore()
    ui.pushToast('info', 'Section queued for regeneration', `${label} will restart after the active draft chunk completes.`)
  }

  function runReviewBackground() {
    const ui = useUiStore()
    reviewBackgrounded.value = true
    ui.pushToast('info', 'Review running in background', 'taskStore keeps the SSE connection alive.', 'Open', 10000)
  }

  function cancelReview() {
    const ui = useUiStore()
    reviewRunning.value = false
    ui.pushToast('warning', 'Review cancelled', 'POST /v1/tasks/rev_2405/cancel returned 202.', 'Resume', 6000)
  }

  return {
    reviewRunning,
    reviewBackgrounded,
    reviewProgress,
    taskTick,
    draftTokens,
    selectedCitation,
    highlightedCitation,
    pipelineSteps,
    liveCitations,
    runStats,
    startTaskRuntime,
    stopTaskRuntime,
    activateCitation,
    regenerateSection,
    runReviewBackground,
    cancelReview,
  }
})
