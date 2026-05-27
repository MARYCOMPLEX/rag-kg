import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { reviewCitations, reviewPipelineSteps, reviewRunStats } from '../mocks/review'
import { useUiStore } from './ui'

export const useReviewStore = defineStore('review', () => {
  const usesApiData = computed(() => import.meta.env.VITE_DATA_SOURCE === 'api')
  const apiMode = usesApiData.value
  const reviewRunning = ref(!apiMode)
  const reviewBackgrounded = ref(false)
  const reviewProgress = ref(apiMode ? 0 : 47)
  const taskTick = ref(0)
  const draftTokens = ref(apiMode ? 0 : 324)
  const selectedCitation = ref(apiMode ? '' : '5')
  const highlightedCitation = ref(apiMode ? '' : '5')

  const pipelineSteps = computed(() => usesApiData.value ? [] : reviewPipelineSteps)
  const liveCitations = computed(() => usesApiData.value ? [] : reviewCitations)
  const runStats = computed(() => usesApiData.value ? [] : reviewRunStats)

  let taskTimer: number | null = null
  let citationHighlightTimer: number | null = null

  function startTaskRuntime() {
    if (usesApiData.value)
      return

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
    if (!liveCitations.value.some(citation => citation.id === id))
      return

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
    if (usesApiData.value) {
      ui.pushToast('info', 'Review API pending', 'OpenAPI must define review run and regeneration endpoints before sections can be regenerated.')
      return
    }

    ui.pushToast('info', 'Section queued for regeneration', `${label} will restart after the active draft chunk completes.`)
  }

  function runReviewBackground() {
    const ui = useUiStore()
    if (usesApiData.value) {
      ui.pushToast('info', 'Review API pending', 'OpenAPI must define review run streaming before background execution can start.')
      return
    }

    reviewBackgrounded.value = true
    ui.pushToast('info', 'Review running in background', 'Mock runtime keeps local progress active.', 'Open', 10000)
  }

  function cancelReview() {
    const ui = useUiStore()
    if (usesApiData.value) {
      ui.pushToast('info', 'Review API pending', 'OpenAPI must define review cancellation before a run can be cancelled.')
      return
    }

    reviewRunning.value = false
    ui.pushToast('warning', 'Review cancelled', 'Mock review generation paused.', 'Resume', 6000)
  }

  return {
    usesApiData,
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
