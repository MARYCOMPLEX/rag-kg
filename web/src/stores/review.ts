import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import type {
  ReviewCancelRequest,
  ReviewCitation,
  ReviewCreateRequest,
  ReviewDraft,
  ReviewDraftDeltaEvent,
  ReviewPipelineStep,
  ReviewRun,
  ReviewRunStat,
  ReviewSnapshot,
  ReviewStatusEvent,
} from '../domain/review/types'
import { reviewSnapshot } from '../mocks/review'
import { connectReviewStream } from '../services/api/reviewStreamClient'
import { createReviewRepository } from '../services/review/reviewRepository'
import { useUiStore } from './ui'

const reviewRepository = createReviewRepository()
const activeReviewStatuses: ReviewRun['status'][] = ['queued', 'running', 'backgrounded']

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function messageFromError(error: unknown) {
  if (error instanceof Error)
    return error.message

  if (isRecord(error) && typeof error.message === 'string') {
    const code = typeof error.code === 'string' ? error.code : 'REVIEW_STREAM_ERROR'
    const requestId = typeof error.request_id === 'string' ? error.request_id : null
    return requestId
      ? `${error.message} (${code}, request ${requestId})`
      : `${error.message} (${code})`
  }

  if (typeof error === 'string')
    return error

  return 'Review stream failed.'
}

function clone<T>(value: T): T {
  return structuredClone(value)
}

function seedSnapshotForLibrary(libraryId: string): ReviewSnapshot {
  return {
    ...clone(reviewSnapshot),
    run: reviewSnapshot.run ? {
      ...clone(reviewSnapshot.run),
      libraryId,
    } : null,
  }
}

function uniqueStrings(values: string[]) {
  return Array.from(new Set(values))
}

function normalizeDraftDelta(delta: ReviewDraftDeltaEvent) {
  return {
    ...delta,
    citations: delta.citations ? uniqueStrings(delta.citations) : undefined,
  }
}

function isReviewDraft(value: ReviewDraft | null): value is ReviewDraft {
  return value !== null
}

export const useReviewStore = defineStore('review', () => {
  const usesApiData = computed(() => import.meta.env.VITE_DATA_SOURCE === 'api')
  const apiMode = usesApiData.value
  const currentLibraryId = ref('')
  const reviewState = ref<'idle' | 'loading' | 'success' | 'error'>(apiMode ? 'idle' : 'success')
  const reviewError = ref<string | null>(null)
  const currentRun = ref<ReviewRun | null>(apiMode ? null : clone(reviewSnapshot.run))
  const pipelineSteps = ref<ReviewPipelineStep[]>(apiMode ? [] : clone(reviewSnapshot.pipelineSteps))
  const liveCitations = ref<ReviewCitation[]>(apiMode ? [] : clone(reviewSnapshot.citations))
  const runStats = ref<ReviewRunStat[]>(apiMode ? [] : clone(reviewSnapshot.runStats))
  const draftContent = ref<ReviewDraft | null>(apiMode ? null : clone(reviewSnapshot.draft))
  const reviewRunning = ref(!apiMode)
  const reviewBackgrounded = ref(false)
  const reviewProgress = ref(apiMode ? 0 : reviewSnapshot.run?.progress ?? 0)
  const taskTick = ref(0)
  const draftTokens = ref(apiMode ? 0 : reviewSnapshot.draft?.draftTokens ?? 0)
  const selectedCitation = ref(apiMode ? '' : reviewSnapshot.citations[0]?.id ?? '')
  const highlightedCitation = ref(apiMode ? '' : reviewSnapshot.citations[0]?.id ?? '')

  let taskTimer: number | null = null
  let citationHighlightTimer: number | null = null
  let activeStream: ReturnType<typeof connectReviewStream> | null = null

  const activeCitation = computed(() => selectedCitation.value)
  const hasCurrentRun = computed(() => currentRun.value !== null)
  const draftHasContent = computed(() => isReviewDraft(draftContent.value))

  function clearStreamTimer() {
    if (taskTimer)
      window.clearInterval(taskTimer)
    taskTimer = null
  }

  function disconnectStream() {
    activeStream?.close()
    activeStream = null
  }

  function setSelectionFromCitations(citations: ReviewCitation[]) {
    const nextId = citations[0]?.id ?? ''
    selectedCitation.value = nextId
    highlightedCitation.value = nextId
  }

  function syncRunState(run: ReviewRun | null) {
    currentRun.value = run ? clone(run) : null
    reviewRunning.value = !!run && activeReviewStatuses.includes(run.status)
    reviewBackgrounded.value = !!run && (run.status === 'backgrounded' || run.backgrounded === true)
    reviewProgress.value = run?.progress ?? 0
  }

  function syncDraft(nextDraft: ReviewDraft | null) {
    draftContent.value = nextDraft ? clone(nextDraft) : null
    draftTokens.value = nextDraft?.draftTokens ?? 0
  }

  function applySnapshot(snapshot: ReviewSnapshot) {
    syncRunState(snapshot.run)
    pipelineSteps.value = clone(snapshot.pipelineSteps)
    runStats.value = clone(snapshot.runStats)
    liveCitations.value = clone(snapshot.citations)
    syncDraft(snapshot.draft)
    setSelectionFromCitations(snapshot.citations)
  }

  function applyCitations(nextCitations: ReviewCitation[]) {
    liveCitations.value = clone(nextCitations)
    setSelectionFromCitations(nextCitations)
  }

  function applyPipeline(nextSteps: ReviewPipelineStep[]) {
    pipelineSteps.value = clone(nextSteps)
  }

  function applyRunStats(nextStats: ReviewRunStat[]) {
    runStats.value = clone(nextStats)
  }

  function applyDraftDelta(delta: ReviewDraftDeltaEvent) {
    const draft = draftContent.value
    if (!draft)
      return

    const normalized = normalizeDraftDelta(delta)
    const nextSections = draft.sections.map((section) => {
      if (section.id !== normalized.sectionId)
        return section

      return {
        ...section,
        markdown: `${section.markdown}${normalized.markdownDelta}`,
        citations: normalized.citations ? uniqueStrings([...section.citations, ...normalized.citations]) : section.citations,
      }
    })

    const nextDraft: ReviewDraft = {
      ...draft,
      sections: nextSections.some(section => section.id === normalized.sectionId)
        ? nextSections
        : [
            ...nextSections,
            {
              id: normalized.sectionId,
              heading: normalized.sectionId,
              markdown: normalized.markdownDelta,
              citations: normalized.citations ?? [],
            },
          ],
      draftTokens: typeof normalized.draftTokens === 'number' ? normalized.draftTokens : draft.draftTokens,
    }

    draftContent.value = nextDraft
    if (typeof normalized.draftTokens === 'number')
      draftTokens.value = normalized.draftTokens
  }

  function applyStatus(status: ReviewStatusEvent) {
    if (!currentRun.value)
      return

    const nextRun: ReviewRun = {
      ...currentRun.value,
      status: status.status,
      progress: typeof status.progress === 'number' ? status.progress : currentRun.value.progress,
      backgrounded: status.status === 'backgrounded',
    }

    syncRunState(nextRun)

    if (typeof status.draftTokens === 'number') {
      draftTokens.value = status.draftTokens
      const draft = draftContent.value
      if (draft) {
        draftContent.value = {
          ...draft,
          draftTokens: status.draftTokens,
        }
      }
    }

    if (typeof status.statusLabel === 'string') {
      const draft = draftContent.value
      if (!draft)
        return

      draftContent.value = {
        ...draft,
        statusLabel: status.statusLabel,
      }
    }
  }

  function openReviewStream(streamUrl: string) {
    disconnectStream()
    activeStream = connectReviewStream(streamUrl, {
      onDraftDelta(delta) {
        applyDraftDelta(delta)
      },
      onPipeline(steps) {
        applyPipeline(steps)
      },
      onCitations(citations) {
        applyCitations(citations)
      },
      onStats(stats) {
        applyRunStats(stats)
      },
      onStatus(status) {
        applyStatus(status)
      },
      onDone(status) {
        applyStatus(status)
        disconnectStream()
      },
      onError(error) {
        const ui = useUiStore()
        const message = messageFromError(error)
        reviewError.value = message
        if (currentRun.value)
          syncRunState({ ...currentRun.value, status: 'failed', backgrounded: false })
        disconnectStream()
        ui.pushToast('danger', 'Review stream failed', message, 'Retry')
      },
    })
  }

  async function loadReview(nextLibraryId: string, force = false) {
    if (!force && currentLibraryId.value === nextLibraryId && reviewState.value === 'success')
      return

    currentLibraryId.value = nextLibraryId
    reviewError.value = null
    disconnectStream()

    if (!usesApiData.value) {
      applySnapshot(seedSnapshotForLibrary(nextLibraryId))
      reviewState.value = 'success'
      return
    }

    reviewState.value = 'loading'
    syncRunState(null)
    pipelineSteps.value = []
    runStats.value = []
    liveCitations.value = []
    syncDraft(null)
    selectedCitation.value = ''
    highlightedCitation.value = ''

    try {
      const snapshot = await reviewRepository.getCurrent(nextLibraryId)
      if (currentLibraryId.value !== nextLibraryId)
        return

      if (snapshot.run === null) {
        applySnapshot({
          run: null,
          pipelineSteps: [],
          runStats: [],
          citations: [],
          draft: null,
          streamUrl: null,
        })
        reviewState.value = 'success'
        return
      }

      applySnapshot(snapshot)
      reviewState.value = 'success'

      const streamUrl = snapshot.streamUrl ?? snapshot.run.streamUrl
      if (streamUrl)
        openReviewStream(streamUrl)
    }
    catch (error) {
      if (currentLibraryId.value !== nextLibraryId)
        return

      reviewState.value = 'error'
      reviewError.value = error instanceof Error ? error.message : 'Unable to load review.'
    }
  }

  async function createReview(request: ReviewCreateRequest = {}) {
    const ui = useUiStore()
    if (!usesApiData.value) {
      ui.pushToast('info', 'Review API pending', 'OpenAPI must define review run creation before the empty state can start a real run.')
      return
    }

    if (!currentLibraryId.value)
      return

    reviewState.value = 'loading'
    reviewError.value = null

    try {
      const snapshot = await reviewRepository.createReview(currentLibraryId.value, request)
      if (snapshot.run && currentLibraryId.value !== snapshot.run.libraryId)
        return

      applySnapshot(snapshot)
      reviewState.value = 'success'

      const streamUrl = snapshot.streamUrl ?? snapshot.run?.streamUrl
      if (streamUrl)
        openReviewStream(streamUrl)
    }
    catch (error) {
      reviewState.value = 'error'
      reviewError.value = error instanceof Error ? error.message : 'Unable to start review.'
      ui.pushToast('danger', 'Review start failed', reviewError.value, 'Retry')
    }
  }

  async function regenerateSection(sectionId: string) {
    const ui = useUiStore()
    if (!usesApiData.value) {
      const stepLabel = pipelineSteps.value.find(step => step.id === sectionId)?.label ?? sectionId
      ui.pushToast('info', 'Section queued for regeneration', `${stepLabel} will restart after the active draft chunk completes.`)
      return
    }

    if (!currentLibraryId.value || !currentRun.value) {
      ui.pushToast('warning', 'Review unavailable', 'Load an active review run before regenerating a section.')
      return
    }

    try {
      reviewError.value = null
      const snapshot = await reviewRepository.regenerateSection(
        currentLibraryId.value,
        currentRun.value.id,
        sectionId,
        { keepCompletedSections: true },
      )

      applySnapshot(snapshot)
      reviewState.value = 'success'

      const streamUrl = snapshot.streamUrl ?? snapshot.run?.streamUrl
      if (streamUrl)
        openReviewStream(streamUrl)
    }
    catch (error) {
      const message = error instanceof Error ? error.message : 'Unable to regenerate the section.'
      reviewError.value = message
      ui.pushToast('danger', 'Review regeneration failed', message, 'Retry')
    }
  }

  function runReviewBackground() {
    const ui = useUiStore()
    if (usesApiData.value) {
      ui.pushToast('info', 'Review backgrounding is handled by the backend.', 'The active run will surface background state from the stream.')
      return
    }

    if (currentRun.value)
      syncRunState({ ...currentRun.value, status: 'backgrounded', backgrounded: true })
    ui.pushToast('info', 'Review running in background', 'Mock runtime keeps local progress active.', 'Open', 10000)
  }

  async function cancelReview(request: ReviewCancelRequest = { keepGeneratedSections: true }) {
    const ui = useUiStore()
    if (!usesApiData.value) {
      if (currentRun.value)
        syncRunState({ ...currentRun.value, status: 'cancelled', backgrounded: false })
      ui.pushToast('warning', 'Review cancelled', 'Mock review generation paused.', 'Resume', 6000)
      return
    }

    if (!currentLibraryId.value || !currentRun.value) {
      ui.pushToast('warning', 'Review unavailable', 'Load an active review run before cancelling it.')
      return
    }

    try {
      reviewError.value = null
      const response = await reviewRepository.cancelReview(currentLibraryId.value, currentRun.value.id, request)
      if (response.run)
        syncRunState(response.run)
      else
        syncRunState({
          ...currentRun.value,
          status: 'cancelled',
          backgrounded: false,
        })

      reviewState.value = 'success'
      disconnectStream()
      ui.pushToast(response.tone, response.title, response.detail, response.action)
    }
    catch (error) {
      const message = error instanceof Error ? error.message : 'Unable to cancel the review.'
      reviewError.value = message
      ui.pushToast('danger', 'Review cancellation failed', message, 'Retry')
    }
  }

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
        if (draftContent.value) {
          draftContent.value = {
            ...draftContent.value,
            draftTokens: draftTokens.value,
          }
        }
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

  return {
    usesApiData,
    currentLibraryId,
    reviewState,
    reviewError,
    currentRun,
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
    draftContent,
    activeCitation,
    hasCurrentRun,
    draftHasContent,
    loadReview,
    createReview,
    regenerateSection,
    runReviewBackground,
    cancelReview,
    startTaskRuntime,
    stopTaskRuntime,
    activateCitation,
    clearStreamTimer,
    disconnectStream,
  }
})
