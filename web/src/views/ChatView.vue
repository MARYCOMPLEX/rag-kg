<script setup lang="ts">
import { nextTick, onMounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import AppIcon from '../components/base/AppIcon.vue'
import { useChatStore } from '../stores/chat'
import { useUiStore } from '../stores/ui'

const chat = useChatStore()
const ui = useUiStore()
const {
  activeCitation,
  autoScrollPaused,
  composerText,
  evidenceList,
  messages,
  streamState,
  usesApiData,
} = storeToRefs(chat)
const { costExceeded } = storeToRefs(ui)
const reasoningOpen = ref(false)
const composerMinHeight = 62
const composerMaxHeight = 220

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

onMounted(() => {
  void nextTick(resizeComposer)
})
</script>

<template>
  <section class="screen chat-screen">
    <section class="conversation">
      <div class="chat-head">
        <span>{{ usesApiData ? 'Session unavailable' : 'Session / 2026-05-05 / 14:32' }}</span>
        <h1>{{ usesApiData ? 'Chat contract pending' : 'How does GraphRAG combine community summarization and vector retrieval?' }}</h1>
      </div>

      <div class="messages" @scroll="autoScrollPaused = true">
        <div v-if="usesApiData" class="chat-pending-state" role="status">
          <AppIcon name="chat" :size="24" />
          <h2>Chat is waiting for backend contract</h2>
          <p>
            API mode hides seeded messages, citation evidence, and simulated token streaming until
            <code>/api/libraries/{libraryId}/chat/session</code>,
            <code>/api/libraries/{libraryId}/chat/questions</code>, and the stream events are defined.
          </p>
        </div>
        <article v-for="message in messages" :key="message.id" class="message" :class="message.role">
          <div class="bubble-avatar">
            {{ message.role === 'user' ? 'YU' : 'AI' }}
          </div>
          <div class="bubble">
            <button v-if="message.role === 'assistant'" class="reasoning-toggle" type="button" @click="reasoningOpen = !reasoningOpen">
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
            <p>{{ message.text }}<span v-if="message.status === 'streaming'" class="stream-caret" /></p>
            <div v-if="message.role === 'assistant'" class="citation-row">
              <button
                v-for="citation in message.citations"
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
        Down 8 new tokens
      </button>

      <div class="composer">
        <textarea
          :ref="setComposerRef"
          v-model="composerText"
          aria-label="Ask anything"
          :disabled="usesApiData"
          :placeholder="usesApiData ? 'Chat API contract pending' : 'Ask anything in this Library... type / for commands'"
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
          <span class="composer-hint">{{ usesApiData ? 'Waiting for OpenAPI chat contract' : 'Cmd + Enter to send' }}</span>
          <button
            class="send-btn"
            :disabled="usesApiData || costExceeded"
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
          <small>{{ usesApiData ? 'No backend evidence loaded' : '3 sources cited / click [n] in answer to jump' }}</small>
        </div>
        <button type="button">Collapse</button>
      </div>
      <div class="evidence-list">
        <div v-if="usesApiData" class="chat-pending-state compact" role="status">
          <AppIcon name="info" :size="20" />
          <h2>Evidence unavailable</h2>
          <p>Grounded evidence remains hidden in API mode until the chat session endpoint returns real records.</p>
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
          <small>{{ item.meta }} / cited 14 times / score {{ item.score }}</small>
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
.chat-pending-state {
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

.chat-pending-state h2 {
  margin: 0;
  color: var(--color-text-primary);
  font-size: 1rem;
}

.chat-pending-state p {
  max-width: 620px;
  margin: 0;
  line-height: 1.6;
}

.chat-pending-state code {
  color: var(--color-text-primary);
  font-size: 0.86em;
}

.chat-pending-state.compact {
  min-height: 220px;
  padding: 22px;
}
</style>
