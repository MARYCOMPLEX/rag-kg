import { computed, nextTick, ref } from 'vue'
import { defineStore } from 'pinia'
import { evidence, groundedAnswerTokens, initialMessages } from '../mocks/chat'
import type { ChatMessage, Evidence, StreamState } from '../types/application'
import { useUiStore } from './ui'

export const useChatStore = defineStore('chat', () => {
  const evidenceList = ref<Evidence[]>(evidence)
  const messages = ref<ChatMessage[]>(initialMessages.map(message => ({ ...message })))
  const activeCitation = ref('1')
  const composerText = ref('')
  const streamState = ref<StreamState>('done')
  const autoScrollPaused = ref(false)
  const composerRef = ref<HTMLTextAreaElement | null>(null)

  const activeEvidence = computed<Evidence>(() => {
    return evidenceList.value.find(item => item.id === activeCitation.value) ?? evidenceList.value[0]!
  })

  let streamTimer: number | null = null

  function clearStreamTimer() {
    if (streamTimer)
      window.clearInterval(streamTimer)
    streamTimer = null
  }

  function sendQuestion(text?: string) {
    const ui = useUiStore()
    if (ui.costExceeded) {
      ui.pushToast('danger', 'Budget exceeded', 'Daily cap reached. Adjust budget or wait until reset.', 'Settings', 0)
      return
    }

    const prompt = (text ?? composerText.value).trim()
    if (!prompt)
      return

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
      assistant.text += `${groundedAnswerTokens[index] ?? ''} `
      index += 1

      if (index === 8)
        assistant.citations = ['?']

      if (index >= groundedAnswerTokens.length) {
        clearStreamTimer()
        assistant.status = 'done'
        assistant.citations = ['1', '2']
        streamState.value = 'done'
        activeCitation.value = '1'
        ui.pushToast('success', 'Answer grounded', '2 citations linked to EvidencePanel', 'Inspect')
      }
    }, 90)
  }

  function stopStream() {
    clearStreamTimer()
    const last = [...messages.value].reverse().find(message => message.role === 'assistant')
    if (last) {
      last.status = 'interrupted'
      last.text = last.text.trim() || 'Generation stopped before the first paragraph was complete.'
    }
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
    evidenceList,
    messages,
    activeCitation,
    activeEvidence,
    composerText,
    streamState,
    autoScrollPaused,
    composerRef,
    sendQuestion,
    stopStream,
    continueStream,
    focusComposer,
    activateCitation,
    handleComposerKey,
    clearStreamTimer,
  }
})
