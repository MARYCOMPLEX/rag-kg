<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { storeToRefs } from 'pinia'
import { useWorkspaceNavigation } from '../../app/useWorkspaceNavigation'
import AppIcon from '../base/AppIcon.vue'
import BaseRichDropdown from '../base/BaseRichDropdown.vue'
import { useLibraryStore } from '../../stores/library'
import { useUiStore } from '../../stores/ui'
import type { ScreenId } from '../../types/application'

interface LibraryDropdownOption {
  value: string
  label: string
  meta?: string
}

const ui = useUiStore()
const library = useLibraryStore()
const { routeScreen, goToScreen } = useWorkspaceNavigation()
const { activeLibrary, error, libraries, loading } = storeToRefs(library)

const sectionLabels: Record<ScreenId, string> = {
  dashboard: 'Libraries',
  chat: 'Chat',
  graph: 'Knowledge Graph',
  docs: 'Documents',
  review: 'Review',
  eval: 'Evaluation',
}

const currentSection = computed(() => sectionLabels[routeScreen.value])
const isOverview = computed(() => routeScreen.value === 'dashboard')
const libraryPlaceholder = computed(() => {
  if (loading.value && !libraries.value.length)
    return 'Loading libraries...'
  if (error.value && !libraries.value.length)
    return 'Libraries unavailable'
  return 'Select library'
})

const libraryOptions = computed(() => {
  return libraries.value.map(item => ({
    value: item.id,
    label: item.name,
    meta: `${item.documentCountLabel} docs`,
  }))
})

function getLibraryAccent(value?: string) {
  return libraries.value.find(item => item.id === value)?.accent ?? 'concept'
}

async function selectLibrary(option: LibraryDropdownOption) {
  library.selectLibrary(option.value)

  if (!isOverview.value)
    await goToScreen(routeScreen.value)
}

onMounted(() => {
  void library.loadLibraries()
})
</script>

<template>
  <header class="top-bar">
    <div class="top-left">
      <button class="brand-block" type="button" aria-label="Go to libraries" @click="goToScreen('dashboard')">
        <span class="brand-logo"><AppIcon name="diamond" :size="18" /></span>
        <strong>RAG-KG Copilot</strong>
      </button>

      <span class="top-divider" />

      <BaseRichDropdown
        class="top-library-dropdown"
        :model-value="activeLibrary"
        :options="libraryOptions"
        :placeholder="libraryPlaceholder"
        aria-label="Select research library"
        @select="selectLibrary"
      >
        <template #trigger-icon="{ option }">
          <span class="library-color-dot" :class="getLibraryAccent(option?.value)" />
        </template>

        <template #option-icon="{ option }">
          <span class="library-color-dot" :class="getLibraryAccent(option.value)" />
        </template>

        <template #action="{ close }">
          <button
            class="library-dropdown-action"
            type="button"
            @click="close(); ui.openCreateLibrary()"
          >
            <AppIcon name="plus" :size="22" />
            <span>New Library</span>
          </button>
        </template>
      </BaseRichDropdown>

      <template v-if="!isOverview">
        <span class="crumb-separator">/</span>
        <span class="crumb-section">{{ currentSection }}</span>
      </template>
    </div>

    <nav class="crumbs" aria-label="Breadcrumb">
      <span>Libraries</span>
      <template v-if="!isOverview">
        <span>/</span>
        <strong>{{ currentSection }}</strong>
      </template>
    </nav>

    <div class="top-actions">
      <button class="search-trigger" type="button" @click="ui.openCommand">
        <AppIcon name="search" :size="15" />
        <span>Search...</span>
        <kbd>Cmd+K</kbd>
      </button>
      <button class="icon-btn" type="button" aria-label="Shortcuts" @click="ui.shortcutsOpen = true">
        <AppIcon name="keyboard" :size="18" />
      </button>
      <button
        class="icon-btn has-dot"
        type="button"
        aria-label="Notifications"
        @click="ui.pushToast('info', 'Notification center', '2 background streams are active.', 'Open')"
      >
        <AppIcon name="bell" :size="18" />
      </button>
      <button class="i18n-btn" type="button">
        EN
        <AppIcon name="chevron" :size="12" />
      </button>
      <button class="avatar" type="button" aria-label="Account">
        RL
      </button>
    </div>
  </header>
</template>

<style scoped>
.top-library-dropdown {
  --rich-dropdown-width: clamp(220px, 21vw, 300px);
  --rich-dropdown-trigger-height: 44px;
  --rich-dropdown-radius: var(--radius-field);
  --rich-dropdown-panel-radius: var(--radius-field);
  --rich-dropdown-font-size: 16px;
}

.library-color-dot {
  display: block;
  width: 13px;
  height: 13px;
  border-radius: var(--radius-indicator);
  background: var(--color-primary-container);
  box-shadow: var(--shadow-dot-contrast);
}

.library-color-dot.method {
  background: var(--color-success);
}

.library-color-dot.dataset {
  background: var(--color-warning);
}

.library-color-dot.citation {
  background: var(--color-citation);
}

.library-color-dot.author {
  background: var(--color-kg-author);
}

.library-dropdown-action {
  display: inline-flex;
  align-items: center;
  width: 100%;
  min-height: 52px;
  gap: 16px;
  border: 0;
  border-radius: var(--radius-control);
  background: transparent;
  padding: 0 18px;
  color: var(--color-primary-container);
  font-size: 15px;
  font-weight: 800;
  letter-spacing: 0;
}

.library-dropdown-action:hover,
.library-dropdown-action:focus-visible {
  background: var(--color-alpha-primary-8);
  outline: none;
}

@media (max-width: 1180px) {
  .top-library-dropdown {
    --rich-dropdown-width: clamp(220px, 24vw, 260px);
  }
}

@media (max-width: 860px) {
  .top-library-dropdown {
    display: none;
  }
}
</style>
