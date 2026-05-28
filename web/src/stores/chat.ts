import { computed, nextTick, ref } from 'vue'
import { defineStore } from 'pinia'
import type { ChatRequestState } from '../domain/chat/types'
import { evidence, groundedAnswerTokens, initialMessages } from '../mocks/chat'
import { connectTaskStream } from '../services/api/taskStreamClient'
import { createChatRepository } from '../services/chat/chatRepository'
import type { ChatMessage, Evidence, StreamState } from '../types/application'
import { useUiStore } from './ui'

const chatRepository = createChatRepository()

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function messageFromError(error: unknown) {
  if (error instanceof Error)
    return error.message

  if (isRecord(error) && typeof error.message === 'string') {
    const code = typeof error.code === 'string' ? error.code : 'STREAM_ERROR'
    const requestId = typeof error.request_id === 'string' ? error.request_id : null
    return requestId
      ? `${error.message} (${code}, request ${requestId})`
      : `${error.message} (${code})`
  }

  if (typeof error === 'string')
    return error

  return 'Chat stream failed.'
}

export const useChatStore = defineStore('chat', () => {
  const usesApiData = computed(() => import.meta.env.VITE_DATA_SOURCE === 'api')
  const apiMode = usesApiData.value
  const sessionId = ref('')
  const sessionTitle = ref(apiMode ? '' : 'How does GraphRAG combine community summarization and vector retrieval?')
  const sessionCreatedAtLabel = ref(apiMode ? '' : '2026-05-05 14:32')
  const sessionState = ref<ChatRequestState>(apiMode ? 'idle' : 'success')
  const sessionError = ref<string | null>(null)
  const currentLibraryId = ref('')
  const evidenceList = ref<Evidence[]>(apiMode ? [] : evidence)
  const messages = ref<ChatMessage[]>(apiMode ? [] : initialMessages.map(message => ({ ...message })))
  const activeCitation = ref(apiMode ? '' : '1')
  const composerText = ref('')
  const streamState = ref<StreamState>(apiMode ? 'idle' : 'done')
  const streamError = ref<string | null>(null)
  const streamingMessageId = ref('')
  const streamingText = ref('')
  const streamingCitationIds = ref<string[]>([])
  const autoScrollPaused = ref(false)
  const composerRef = ref<HTMLTextAreaElement | null>(null)

  const activeEvidence = computed<Evidence | null>(() => {
    return evidenceList.value.find(item => item.id === activeCitation.value) ?? evidenceList.value[0] ?? null
  })

  let streamTimer: number | null = null
  let activeStream: ReturnType<typeof connectTaskStream> | null = null
  let activeAssistantIndex: number | null = null

  function clearStreamTimer() {
    if (streamTimer)
      window.clearInterval(streamTimer)
    streamTimer = null
  }

  function disconnectStream() {
    activeStream?.close()
    activeStream = null
    activeAssistantIndex = null
  }

  function resetSessionState() {
    sessionId.value = ''
    sessionTitle.value = ''
    sessionCreatedAtLabel.value = ''
    evidenceList.value = []
    messages.value = []
    activeCitation.value = ''
    streamState.value = 'idle'
    streamError.value = null
    streamingMessageId.value = ''
    streamingText.value = ''
    streamingCitationIds.value = []
    disconnectStream()
    clearStreamTimer()
  }

  function mergeEvidence(nextEvidence: Evidence[]) {
    if (!nextEvidence.length)
      return

    const existing = new Map(evidenceList.value.map(item => [item.id, item]))
    nextEvidence.forEach((item) => {
      existing.set(item.id, item)
    })
    evidenceList.value = Array.from(existing.values())
    if (!activeCitation.value)
      activeCitation.value = nextEvidence[0]?.id ?? evidenceList.value[0]?.id ?? ''
  }

  function updateAssistant(updater: (message: ChatMessage) => ChatMessage) {
    if (activeAssistantIndex === null)
      return

    messages.value = messages.value.map((message, index) => {
      if (index !== activeAssistantIndex || message.role !== 'assistant')
        return message

      return updater({ ...message, citations: message.citations ? [...message.citations] : message.citations })
    })
  }

  async function loadSession(nextLibraryId: string, force = false) {
    if (!force && currentLibraryId.value === nextLibraryId && sessionState.value === 'success')
      return

    currentLibraryId.value = nextLibraryId
    sessionState.value = 'loading'
    sessionError.value = null
    resetSessionState()

    try {
      const session = await chatRepository.getSession(nextLibraryId)
      if (currentLibraryId.value !== nextLibraryId)
        return

      sessionId.value = session.sessionId
      sessionTitle.value = session.title
      sessionCreatedAtLabel.value = session.createdAtLabel
      messages.value = session.messages
      evidenceList.value = session.evidence
      activeCitation.value = session.evidence[0]?.id ?? ''
      streamingMessageId.value = ''
      streamingText.value = ''
      streamingCitationIds.value = []
      streamState.value = 'idle'
      sessionState.value = 'success'
    }
    catch (error) {
      if (currentLibraryId.value !== nextLibraryId)
        return

      sessionError.value = error instanceof Error ? error.message : 'Unable to load chat session.'
      sessionState.value = 'error'
    }
  }

  async function sendApiQuestion(prompt: string) {
    const ui = useUiStore()
    disconnectStream()
    streamError.value = null
    streamState.value = 'streaming'

    try {
      const response = await chatRepository.createQuestion(currentLibraryId.value, {
        question: prompt,
        sessionId: sessionId.value || undefined,
      })

      messages.value.push(response.userMessage, response.assistantMessage)
      mergeEvidence(response.evidence)
      activeAssistantIndex = messages.value.length - 1
      streamingMessageId.value = response.assistantMessage.id
      streamingText.value = ''
      streamingCitationIds.value = []
      composerText.value = ''
      autoScrollPaused.value = false

      activeStream = connectTaskStream(response.streamUrl, {
        onToken(token) {
          if (!token)
            return

          streamingText.value += token
          updateAssistant(message => ({
            ...message,
            text: `${message.text}${token}`,
          }))
        },
        onEvidence(nextEvidence) {
          mergeEvidence(nextEvidence)
        },
        onCitations(citationIds) {
          if (!citationIds.length)
            return

          streamingCitationIds.value = citationIds
          updateAssistant(message => ({
            ...message,
            citations: citationIds,
          }))
          activeCitation.value = citationIds[0] ?? activeCitation.value
        },
        onStatus(status) {
          updateAssistant(message => ({
              ...message,
              status,
            }))
          streamState.value = status
        },
        onDone(status) {
          updateAssistant(message => ({
              ...message,
              status,
            }))
          streamState.value = status
          disconnectStream()
        },
        onError(error) {
          handleStreamError(error)
        },
      })

      void activeStream.done.catch((error: unknown) => {
        if (error instanceof DOMException && error.name === 'AbortError')
          return

        handleStreamError(error)
      })
    }
    catch (error) {
      const message = messageFromError(error)
      streamError.value = message
      streamState.value = 'interrupted'
      ui.pushToast('danger', 'Chat request failed', message, 'Retry')
    }
  }

  function handleStreamError(error: unknown) {
    const ui = useUiStore()
    const message = messageFromError(error)
    if (streamingMessageId.value) {
      streamingText.value = streamingText.value.trim() || 'Answer stream failed before completion.'
      streamingCitationIds.value = []
    }
    updateAssistant(current => ({
        ...current,
        status: 'interrupted',
        text: current.text.trim() || 'Answer stream failed before completion.',
      }))
    streamError.value = message
    streamState.value = 'interrupted'
    disconnectStream()
    ui.pushToast('danger', 'Chat stream failed', message, 'Retry')
  }

  function sendMockQuestion(prompt: string) {
    clearStreamTimer()
    messages.value.push({ id: `u-${Date.now()}`, role: 'user', text: prompt })

    const assistant: ChatMessage = {
      id: `a-${Date.now()}`,
      role: 'assistant',
      text: '',
      status: 'streaming',
      citations: [],
    }

    messages.value.push(assistant)
    composerText.value = ''
    streamState.value = 'streaming'
    autoScrollPaused.value = false

    let index = 0
    streamTimer = window.setInterval(() => {
      streamingText.value += `${groundedAnswerTokens[index] ?? ''} `
      updateAssistant(current => ({
        ...current,
        text: `${current.text}${groundedAnswerTokens[index] ?? ''} `,
      }))
      index += 1

      if (index === 8)
        streamingCitationIds.value = ['?']
        updateAssistant(current => ({
          ...current,
          citations: ['?'],
        }))

      if (index >= groundedAnswerTokens.length) {
        clearStreamTimer()
        streamingCitationIds.value = ['1', '2']
        updateAssistant(current => ({
          ...current,
          status: 'done',
          citations: ['1', '2'],
        }))
        streamState.value = 'done'
        activeCitation.value = '1'
        useUiStore().pushToast('success', 'Answer grounded', '2 citations linked to EvidencePanel', 'Inspect')
      }
    }, 90)
  }

  function sendQuestion(text?: string) {
    const ui = useUiStore()
    if (ui.costExceeded) {
      ui.pushToast('danger', 'Budget exceeded', 'Daily cap reached. Adjust budget or wait until reset.', 'Settings', 0)
      return
    }

    const prompt = (text ?? composerText.value).trim()
    if (!prompt) {
      ui.pushToast('info', 'Question is empty', 'Enter a question before sending.')
      return
    }

    if (usesApiData.value) {
      void sendApiQuestion(prompt)
      return
    }

    sendMockQuestion(prompt)
  }

  function stopStream() {
    clearStreamTimer()
    disconnectStream()
    if (activeAssistantIndex !== null) {
      updateAssistant(current => ({
        ...current,
        status: 'interrupted',
        text: current.text.trim() || 'Generation stopped before the first paragraph was complete.',
      }))
    }
    if (streamingMessageId.value)
      streamingText.value = streamingText.value.trim() || 'Generation stopped before the first paragraph was complete.'
    streamState.value = 'interrupted'
  }

  function continueStream() {
    composerText.value = 'Continue from the interrupted point with the same evidence constraints.'
    sendQuestion()
  }

  function focusComposer() {
    nextTick(() => composerRef.value?.focus())
  }

  function activateCitation(id: string) {
    if (!evidenceList.value.some(item => item.id === id))
      return

    const ui = useUiStore()
    activeCitation.value = id
    ui.citationPreview = null
  }

  function handleComposerKey(event: KeyboardEvent) {
    const ui = useUiStore()
    if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
      event.preventDefault()
      sendQuestion()
    }

    if (event.key === 'Escape') {
      event.preventDefault()
      composerText.value = ''
      ui.pushToast('info', 'Draft saved', 'Esc Esc cleared the composer and persisted draft state.')
    }
  }

  return {
    usesApiData,
    sessionId,
    sessionTitle,
    sessionCreatedAtLabel,
    sessionState,
    sessionError,
    currentLibraryId,
    streamingMessageId,
    streamingText,
    streamingCitationIds,
    evidenceList,
    messages,
    activeCitation,
    activeEvidence,
    composerText,
    streamState,
    streamError,
    autoScrollPaused,
    composerRef,
    loadSession,
    sendQuestion,
    stopStream,
    continueStream,
    focusComposer,
    activateCitation,
    handleComposerKey,
    clearStreamTimer,
    disconnectStream,
  }
})
