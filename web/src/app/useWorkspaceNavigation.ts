import { computed } from 'vue'
import { storeToRefs } from 'pinia'
import { useRoute, useRouter } from 'vue-router'
import { routeNameScreens, screenRouteNames } from '../router/screenRoutes'
import { useChatStore } from '../stores/chat'
import { useGraphStore } from '../stores/graph'
import { useLibraryStore } from '../stores/library'
import { useUiStore } from '../stores/ui'
import type { ScreenId } from '../types/application'

export function useWorkspaceNavigation() {
  const router = useRouter()
  const route = useRoute()
  const ui = useUiStore()
  const graph = useGraphStore()
  const chat = useChatStore()
  const library = useLibraryStore()
  const { activeLibrary } = storeToRefs(library)

  const routeScreen = computed<ScreenId>(() => {
    const routeName = String(route.name ?? '')
    return routeNameScreens[routeName] ?? 'chat'
  })

  function syncRouteState() {
    ui.setActiveScreen(routeScreen.value)
    const libraryId = route.params.libraryId
    if (typeof libraryId === 'string' && libraryId)
      activeLibrary.value = libraryId
  }

  async function goToScreen(screen: ScreenId) {
    graph.closeContextMenu()
    ui.setActiveScreen(screen)

    if (screen === 'dashboard') {
      await router.push({ name: screenRouteNames.dashboard })
      return
    }

    if (!activeLibrary.value)
      await library.loadLibraries()

    if (!activeLibrary.value) {
      await router.push({ name: screenRouteNames.dashboard })
      return
    }

    await router.push({
      name: screenRouteNames[screen],
      params: { libraryId: activeLibrary.value },
    })
  }

  async function focusComposer() {
    await goToScreen('chat')
    chat.focusComposer()
  }

  return {
    routeScreen,
    syncRouteState,
    goToScreen,
    focusComposer,
  }
}
