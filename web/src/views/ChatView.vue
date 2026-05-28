<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useRoute } from 'vue-router'
import AppIcon from '../components/base/AppIcon.vue'
import { useChatStore } from '../stores/chat'
import { useUiStore } from '../stores/ui'

const chat = useChatStore()
const ui = useUiStore()
const route = useRoute()
const {
  activeCitation,
  autoScrollPaused,
  composerText,
  evidenceList,
  messages,
  sessionCreatedAtLabel,
  sessionError,
  sessionState,
  sessionTitle,
  streamingCitationIds,
  streamingMessageId,
  streamingText,
  streamError,
  streamState,
  usesApiData,
} = storeToRefs(chat)
const { costExceeded } = storeToRefs(ui)
const reasoningOpen = ref(false)
const composerMinHeight = 62
const composerMaxHeight = 220
const libraryId = computed(() => String(route.params.libraryId ?? ''))
const sessionReady = computed(() => !usesApiData.value || sessionState.value === 'success')
const composerDisabled = computed(() => costExceeded.value || !sessionReady.value || streamState.value === 'streaming')
const canSubmit = computed(() => {
  if (streamState.value === 'streaming')
    return true

  return !composerDisabled.value && composerText.value.trim().length > 0
})

function messageText(message: { id: string; text: string }) {
  if (message.id === streamingMessageId.value && streamingText.value)
    return streamingText.value

  return message.text
}

function messageCitations(message: { id: string; citations?: string[] }) {
  if (message.id === streamingMessageId.value && streamingCitationIds.value.length)
    return streamingCitationIds.value

  return message.citations ?? []
}

function resizeComposer() {
  const element = chat.composerRef
  if (!element)
    return

  element.style.height = 'auto'
  const nextHeight = Math.max(composerMinHeight, Math.min(element.scrollHeight, composerMaxHeight))
  element.style.height = `${nextHeight}px`
  element.style.overflowY = element.scrollHeight > composerMaxHeight ? 'auto' : 'hidden'
}

function setComposerRef(element: unknown) {
  chat.composerRef = element as HTMLTextAreaElement | null
  void nextTick(resizeComposer)
}

watch(composerText, () => {
  void nextTick(resizeComposer)
})

watch(libraryId, (nextLibraryId) => {
  if (nextLibraryId)
    void chat.loadSession(nextLibraryId)
}, { immediate: true })

onMounted(() => {
  void nextTick(resizeComposer)
})

onBeforeUnmount(() => {
  chat.disconnectStream()
})
</script>

<template>
  <section class="screen chat-screen">
    <section class="conversation">
      <div class="chat-head">
        <span>{{ sessionCreatedAtLabel ? `Session / ${sessionCreatedAtLabel}` : 'Session' }}</span>
        <h1>{{ sessionTitle || 'New chat' }}</h1>
      </div>

      <div class="messages" @scroll="autoScrollPaused = true">
        <div v-if="sessionState === 'loading'" class="chat-state" role="status">
          <AppIcon name="chat" :size="24" />
          <h2>Loading chat session</h2>
        </div>
        <div v-else-if="sessionState === 'error'" class="chat-state error" role="alert">
          <AppIcon name="warning" :size="24" />
          <h2>Chat session unavailable</h2>
          <p>{{ sessionError }}</p>
          <button type="button" @click="chat.loadSession(libraryId, true)">
            Retry
          </button>
        </div>
        <div v-else-if="usesApiData && !messages.length" class="chat-state" role="status">
          <AppIcon name="chat" :size="24" />
          <h2>New chat</h2>
          <p>Ask a question to start a grounded answer stream.</p>
        </div>
        <article v-for="message in messages" :key="message.id" class="message" :class="message.role">
          <div class="bubble-avatar">
            {{ message.role === 'user' ? 'YU' : 'AI' }}
          </div>
          <div class="bubble">
            <button v-if="message.role === 'assistant' && !usesApiData" class="reasoning-toggle" type="button" @click="reasoningOpen = !reasoningOpen">
              <AppIcon name="reason" :size="14" />
              {{ reasoningOpen ? 'Hide reasoning trace' : 'Show reasoning trace' }}
              <span>/</span>
              <b>6 retrieval steps</b>
              <span>/</span>
              <b>4.2s</b>
              <AppIcon name="chevron" :size="13" />
            </button>
            <div v-if="message.role === 'assistant' && reasoningOpen" class="reasoning-trace">
              route query -> retrieve communities -> expand chunks -> rerank -> verify citations -> synthesize
            </div>
            <p>{{ messageText(message) }}<span v-if="message.status === 'streaming'" class="stream-caret" /></p>
            <div v-if="message.role === 'assistant'" class="citation-row">
              <button
                v-for="citation in messageCitations(message)"
                :key="citation"
                class="citation-chip"
                :class="{ placeholder: citation === '?', active: activeCitation === citation }"
                type="button"
                @mouseenter="citation !== '?' && (ui.citationPreview = citation)"
                @mouseleave="ui.citationPreview = null"
                @focus="citation !== '?' && (ui.citationPreview = citation)"
                @click="citation !== '?' && chat.activateCitation(citation)"
              >
                {{ citation === '?' ? '[?]' : citation }}
              </button>
              <span v-if="message.status === 'streaming'" class="state-pill">event: token</span>
              <span v-if="message.status === 'done'" class="state-pill cyan">event: citations</span>
              <span v-if="message.status === 'unsubstantiated'" class="state-pill">unsubstantiated</span>
            </div>
            <div v-if="message.status === 'interrupted'" class="inline-error">
              Stream interrupted
              <button type="button" @click="chat.sendQuestion('Retry the interrupted answer.')">
                Retry
              </button>
              <button type="button" @click="chat.continueStream">
                Continue from here
              </button>
            </div>
            <div v-if="message.status === 'unsubstantiated'" class="inline-error">
              Cannot answer without evidence.
            </div>
          </div>
        </article>
      </div>

      <button v-if="autoScrollPaused" class="new-token-pill" type="button" @click="autoScrollPaused = false">
        New tokens
      </button>

      <div class="composer">
        <p v-if="streamError" class="composer-error" role="alert">
          {{ streamError }}
        </p>
        <textarea
          :ref="setComposerRef"
          v-model="composerText"
          aria-label="Ask anything"
          :disabled="composerDisabled"
          :placeholder="sessionReady ? 'Ask anything in this Library... type / for commands' : 'Chat session unavailable'"
          @input="resizeComposer"
          @keydown="chat.handleComposerKey"
        />
        <div class="composer-bar">
          <div class="composer-tools">
            <button class="composer-icon" type="button" title="Attach file">
              <AppIcon name="attach" :size="16" />
            </button>
            <button class="composer-icon" type="button" title="Add context">
              <AppIcon name="plus" :size="16" />
            </button>
            <span class="composer-divider" />
            <button class="composer-tool" type="button">
              <AppIcon name="tools" :size="15" />
              Tools
            </button>
          </div>
          <span class="composer-hint">{{ streamState === 'streaming' ? 'Streaming answer' : 'Cmd + Enter to send' }}</span>
          <button
            class="send-btn"
            :disabled="!canSubmit"
            type="button"
            @click="streamState === 'streaming' ? chat.stopStream() : chat.sendQuestion()"
          >
            <AppIcon :name="streamState === 'streaming' ? 'close' : 'send'" :size="16" />
          </button>
        </div>
      </div>
    </section>

    <aside class="evidence-panel">
      <div class="panel-title">
        <div>
          <strong>Evidence</strong>
          <small>{{ evidenceList.length ? `${evidenceList.length} sources cited` : 'No evidence yet' }}</small>
        </div>
        <button type="button">Collapse</button>
      </div>
      <div class="evidence-list">
        <div v-if="sessionState === 'loading'" class="chat-state compact" role="status">
          <AppIcon name="info" :size="20" />
          <h2>Loading evidence</h2>
        </div>
        <div v-else-if="usesApiData && !evidenceList.length" class="chat-state compact" role="status">
          <AppIcon name="info" :size="20" />
          <h2>No evidence yet</h2>
          <p>Evidence appears here when the answer stream emits grounded records.</p>
        </div>
        <article
          v-for="item in evidenceList"
          :key="item.id"
          class="evidence-card"
          :class="{ active: activeCitation === item.id }"
          tabindex="0"
          @click="chat.activateCitation(item.id)"
        >
          <div class="card-line">
            <span class="citation-chip">{{ item.id }}</span>
            <span class="tag">{{ item.label }}</span>
            <button type="button" aria-label="Open source">
              <AppIcon name="external" :size="16" />
            </button>
          </div>
          <h3>{{ item.title }}</h3>
          <p>{{ item.snippet }}</p>
          <small>{{ item.meta }} / score {{ item.score }}</small>
        </article>
        <div v-if="!usesApiData" class="evidence-notes">
          <div>
            <strong>Edge case</strong>
            <span>0-hit retrieval on specific vector sub-query.</span>
          </div>
          <div>
            <strong>System</strong>
            <span>Map-reduce stream auto-recovered.</span>
          </div>
        </div>
      </div>
    </aside>
  </section>
</template>

<style scoped>
.chat-state {
  display: grid;
  gap: 12px;
  place-items: center;
  align-content: center;
  min-height: 280px;
  padding: 28px;
  color: var(--color-text-muted);
  text-align: center;
  border: 1px dashed var(--color-border-muted);
  border-radius: var(--radius-lg);
  background: var(--color-bg-muted);
}

.chat-state.error {
  border-color: var(--color-danger);
}

.chat-state h2 {
  margin: 0;
  color: var(--color-text-primary);
  font-size: 1rem;
}

.chat-state p {
  max-width: 620px;
  margin: 0;
  line-height: 1.6;
}

.chat-state button {
  min-height: 36px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-control);
  background: var(--color-bg-surface);
  padding: 0 14px;
  color: var(--color-text-primary);
  font-weight: 700;
}

.chat-state.compact {
  min-height: 220px;
  padding: 22px;
}

.composer-error {
  margin: 0 0 10px;
  border: 1px solid var(--color-danger);
  border-radius: var(--radius-control);
  padding: 10px 12px;
  color: var(--color-danger);
  font-size: 13px;
  line-height: 18px;
}
</style>
