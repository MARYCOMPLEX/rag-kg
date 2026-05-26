<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, watch } from 'vue'
import { RouterView, useRoute } from 'vue-router'
import SideNav from '../components/layout/SideNav.vue'
import TopBar from '../components/layout/TopBar.vue'
import BackgroundTaskPill from '../components/overlays/BackgroundTaskPill.vue'
import CitationPopover from '../components/overlays/CitationPopover.vue'
import CommandPalette from '../components/overlays/CommandPalette.vue'
import CreateLibraryModal from '../components/overlays/CreateLibraryModal.vue'
import DocumentDrawer from '../components/overlays/DocumentDrawer.vue'
import GraphContextMenu from '../components/overlays/GraphContextMenu.vue'
import ShortcutsModal from '../components/overlays/ShortcutsModal.vue'
import ToastViewport from '../components/overlays/ToastViewport.vue'
import { useWorkspaceNavigation } from './useWorkspaceNavigation'
import { useChatStore } from '../stores/chat'
import { useGraphStore } from '../stores/graph'
import { useReviewStore } from '../stores/review'
import { useUiStore } from '../stores/ui'

const ui = useUiStore()
const chat = useChatStore()
const graph = useGraphStore()
const review = useReviewStore()
const route = useRoute()
const { routeScreen, syncRouteState, goToScreen, focusComposer } = useWorkspaceNavigation()
const hideSidebar = computed(() => route.meta.hideSidebar === true)
const shellClass = computed(() => hideSidebar.value ? 'shell-overview' : 'shell-workspace')

let keyBuffer = ''

watch(routeScreen, syncRouteState, { immediate: true })

function closeFloatingLayer() {
  if (graph.contextMenuOpen) {
    graph.closeContextMenu()
    return true
  }

  if (ui.commandOpen || ui.libraryModalOpen || ui.shortcutsOpen || ui.documentDrawerOpen) {
    ui.closeTopLayer()
    return true
  }

  return false
}

function onGlobalKeydown(event: KeyboardEvent) {
  const target = event.target as HTMLElement | null
  const isTyping = ['INPUT', 'TEXTAREA'].includes(target?.tagName ?? '')

  if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
    event.preventDefault()
    ui.openCommand()
    return
  }

  if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'n') {
    event.preventDefault()
    ui.openCreateLibrary()
    return
  }

  if (event.key === '?' && !isTyping) {
    ui.shortcutsOpen = true
    return
  }

  if (event.key === '/' && !isTyping) {
    event.preventDefault()
    void focusComposer()
    return
  }

  if (event.key === 'Escape') {
    if (closeFloatingLayer())
      return
    if (chat.streamState === 'streaming')
      chat.stopStream()
    return
  }

  if (!isTyping) {
    keyBuffer = `${keyBuffer}${event.key.toLowerCase()}`.slice(-2)
    if (keyBuffer === 'gd')
      void goToScreen('docs')
    if (keyBuffer === 'gc')
      void goToScreen('chat')
    if (keyBuffer === 'gk')
      void goToScreen('graph')
    if (keyBuffer === 'ge')
      void goToScreen('eval')
  }
}

onMounted(() => {
  window.addEventListener('keydown', onGlobalKeydown)
  review.startTaskRuntime()
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onGlobalKeydown)
  chat.clearStreamTimer()
  review.stopTaskRuntime()
})
</script>

<template>
  <main class="prototype-shell" :class="shellClass" @click="graph.closeContextMenu">
    <TopBar />
    <SideNav v-if="!hideSidebar" />
    <section class="workbench">
      <div v-if="ui.costExceeded" class="alert-banner danger">
        <strong>Budget exceeded.</strong>
        Chat send, Review run, Eval run and Re-train are disabled until the budget is changed.
        <button type="button" @click="goToScreen('eval')">
          Adjust budget
        </button>
      </div>

      <RouterView />
    </section>

    <CommandPalette />
    <CreateLibraryModal />
    <ShortcutsModal />
    <DocumentDrawer />
    <CitationPopover />
    <GraphContextMenu />
    <ToastViewport />
    <BackgroundTaskPill />
  </main>
</template>
