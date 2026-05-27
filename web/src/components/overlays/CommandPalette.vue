<script setup lang="ts">
import { computed } from 'vue'
import { storeToRefs } from 'pinia'
import BaseModal from '../base/BaseModal.vue'
import AppIcon from '../base/AppIcon.vue'
import { useWorkspaceNavigation } from '../../app/useWorkspaceNavigation'
import { useSearchStore } from '../../stores/search'
import { useUiStore } from '../../stores/ui'
import type { CommandSearchResult } from '../../types/application'

const ui = useUiStore()
const search = useSearchStore()
const { commandOpen, commandItems, commandQuery } = storeToRefs(ui)
const { documentResults, entityResults } = storeToRefs(search)
const { goToScreen } = useWorkspaceNavigation()

const actionResults = computed<CommandSearchResult[]>(() => commandItems.value.map((item) => ({
  label: item.label,
  meta: item.meta,
  icon: item.screen === 'graph' ? 'graph' : item.screen === 'docs' ? 'file' : item.screen === 'review' ? 'review' : 'search',
  screen: item.screen,
  shortcut: item.shortcut,
})))

const sections = computed(() => {
  const query = commandQuery.value.trim()
  const allSections = [
    { title: 'Entities', items: entityResults.value },
    { title: 'Documents', items: documentResults.value },
    { title: query ? `Actions matching "${query}"` : 'Suggested actions', items: actionResults.value },
  ]

  const normalized = query.toLowerCase()
  return allSections
    .map(section => ({
      ...section,
      items: query
        ? section.items.filter(item =>
            item.label.toLowerCase().includes(normalized)
            || item.meta.toLowerCase().includes(normalized)
            || section.title.toLowerCase().includes(normalized),
          )
        : section.items,
    }))
    .filter(section => section.items.length)
})

function closeCommand() {
  ui.commandOpen = false
}

function selectCommand(screen = sections.value[0]?.items[0]?.screen) {
  if (!screen)
    return

  void goToScreen(screen)
}
</script>

<template>
  <BaseModal
    :show="commandOpen"
    size="command"
    hide-header
    close-label="Close command palette"
    @update:show="ui.commandOpen = $event"
  >
    <template #header>
      <div class="command-search-row">
        <AppIcon name="search" :size="18" />
        <input
          v-model="commandQuery"
          data-autofocus
          role="combobox"
          aria-expanded="true"
          aria-controls="cmdk-list"
          placeholder="Search command, doc, entity, action... prefixes: cmd: doc: entity: lib:*"
          @keydown.enter="selectCommand()"
        >
        <button class="command-esc" type="button" aria-label="Close command palette" @click="closeCommand">
          Esc
        </button>
      </div>
    </template>

    <div id="cmdk-list" class="command-body" role="listbox">
      <section v-for="(section, sectionIndex) in sections" :key="section.title" class="command-section">
        <h3>{{ section.title }}</h3>
        <button
          v-for="(item, itemIndex) in section.items"
          :key="`${section.title}-${item.label}`"
          class="command-result"
          :class="{ active: sectionIndex === 0 && itemIndex === 0 }"
          role="option"
          type="button"
          :aria-selected="sectionIndex === 0 && itemIndex === 0"
          @click="selectCommand(item.screen)"
        >
          <span class="command-leading" :class="item.tone">
            <AppIcon :name="item.icon" :size="16" />
          </span>
          <span class="command-copy">
            <strong>{{ item.label }}</strong>
            <small>{{ item.meta }}</small>
          </span>
          <kbd v-if="item.shortcut">{{ item.shortcut }}</kbd>
          <kbd v-else>Enter</kbd>
        </button>
      </section>

      <div v-if="!sections.length" class="command-empty">
        <AppIcon name="search" :size="18" />
        <span>No commands found in this Library.</span>
      </div>
    </div>

    <template #footer>
      <span class="command-footer-hint">Up/Down navigate</span>
      <span class="command-footer-hint">Enter open</span>
      <span class="command-footer-hint">Tab cycle scope</span>
      <span class="command-footer-hint">Esc close</span>
    </template>
  </BaseModal>
</template>

<style scoped>
.command-search-row {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 12px;
  border-bottom: 1px solid var(--color-outline-variant);
  padding: 0 20px;
}

.command-search-row input {
  width: 100%;
  height: 64px;
  border: 0;
  background: transparent;
  color: var(--color-on-surface);
  font-size: 16px;
  line-height: 22px;
  outline: none;
}

.command-search-row input:focus,
.command-search-row input:focus-visible {
  box-shadow: var(--shadow-none);
  outline: none;
}

.command-search-row input::placeholder {
  color: var(--color-outline);
}

.command-esc,
.command-result kbd {
  border: 1px solid var(--color-outline-variant);
  border-radius: var(--radius-sm);
  background: var(--color-surface-container-low);
  color: var(--color-outline);
  font-family: "JetBrains Mono", monospace;
  font-size: 11px;
  font-weight: 700;
  line-height: 16px;
}

.command-esc {
  min-width: 34px;
  height: 24px;
}

.command-body {
  flex: 1 1 auto;
  min-height: 0;
  overflow-x: hidden;
  overflow-y: auto;
  overscroll-behavior: contain;
  padding: 16px 12px;
}

.command-section + .command-section {
  margin-top: 16px;
}

.command-section h3 {
  margin: 0 0 6px;
  padding: 0 8px;
  color: var(--color-outline);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: .04em;
  line-height: 16px;
  text-transform: uppercase;
}

.command-result {
  display: grid;
  grid-template-columns: 30px minmax(0, 1fr) auto;
  align-items: center;
  width: 100%;
  min-height: 44px;
  gap: 10px;
  border: 0;
  border-radius: var(--radius-card);
  background: transparent;
  padding: 6px 8px;
  text-align: left;
  transition:
    background-color var(--motion-duration-fast) var(--motion-ease-standard),
    color var(--motion-duration-fast) var(--motion-ease-standard);
}

.command-result:hover,
.command-result:focus-visible {
  background: var(--color-surface-container-low);
  outline: none;
}

.command-result.active {
  background: var(--color-primary-fixed);
}

.command-leading {
  display: grid;
  place-items: center;
  width: 30px;
  height: 30px;
  border-radius: var(--radius-control);
  background: var(--color-surface-container);
  color: var(--color-on-surface-variant);
}

.command-leading.concept {
  background: var(--color-primary-fixed);
  color: var(--color-primary);
}

.command-leading.method {
  background: var(--color-success-50-exact);
  color: var(--color-success-700-exact);
}

.command-copy {
  display: grid;
  min-width: 0;
}

.command-copy strong {
  overflow: hidden;
  color: var(--color-on-surface);
  font-size: 14px;
  font-weight: 700;
  line-height: 20px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.command-copy small {
  overflow: hidden;
  color: var(--color-on-surface-variant);
  font-size: 12px;
  line-height: 16px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.command-result kbd {
  padding: 2px 7px;
}

.command-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 180px;
  gap: 8px;
  color: var(--color-on-surface-variant);
  font-size: 13px;
}

.command-footer-hint {
  color: var(--color-outline);
  font-size: 12px;
  line-height: 16px;
}
</style>
