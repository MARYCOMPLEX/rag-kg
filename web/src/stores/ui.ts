import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import {
  mainNavigation,
  screenNavigation,
  commandActionTemplates,
} from '../app/staticNavigation'
import {
  libraryStats,
  recentSessions,
} from '../mocks/navigation'
import { useLibraryStore } from './library'
import type { CommandItem, ScreenId, ToastItem, ToastTone } from '../types/application'

export const useUiStore = defineStore('ui', () => {
  const library = useLibraryStore()
  const screens = screenNavigation
  const activeScreen = ref<ScreenId>('chat')
  const costExceeded = ref(false)
  const commandOpen = ref(false)
  const shortcutsOpen = ref(false)
  const libraryModalOpen = ref(false)
  const documentDrawerOpen = ref(false)
  const drawerPinned = ref(false)
  const citationPreview = ref<string | null>(null)
  const commandQuery = ref('')
  const toastSeq = ref(1)
  const toasts = ref<ToastItem[]>([])

  const currentScreenTitle = computed(() => screens.find(item => item.id === activeScreen.value)?.label ?? 'Chat')
  const mainNavigationItems = computed(() => mainNavigation)
  const recentSessionItems = computed(() => recentSessions)
  const libraryStatItems = computed(() => libraryStats)
  const visibleToasts = computed(() => toasts.value.slice(0, 3))
  const commandItems = computed(() => {
    const query = commandQuery.value.trim().toLowerCase()
    const activeLibrary = library.activeLibrary
    const actions: CommandItem[] = commandActionTemplates.map(item => ({
      label: item.label,
      meta: item.buildMeta(activeLibrary),
      screen: item.screen,
      shortcut: item.shortcut,
    }))

    return actions.filter((item) => {
      return !query || item.label.toLowerCase().includes(query) || item.meta.toLowerCase().includes(query)
    })
  })

  function setActiveScreen(screen: ScreenId) {
    activeScreen.value = screen
    commandOpen.value = false
    if (screen !== 'docs')
      documentDrawerOpen.value = false
  }

  function pushToast(tone: ToastTone, title: string, detail: string, action?: string, timeout = 5000) {
    const item = { id: toastSeq.value++, tone, title, detail, action, timeout }
    const existing = toasts.value.findIndex(toast => toast.title === title)
    if (existing >= 0)
      toasts.value.splice(existing, 1, item)
    else
      toasts.value.unshift(item)

    if (tone !== 'danger') {
      window.setTimeout(() => {
        toasts.value = toasts.value.filter(toast => toast.id !== item.id)
      }, timeout)
    }
  }

  function openCommand() {
    commandOpen.value = true
    commandQuery.value = ''
  }

  function openCreateLibrary() {
    libraryModalOpen.value = true
  }

  function closeTopLayer() {
    if (commandOpen.value)
      commandOpen.value = false
    else if (libraryModalOpen.value)
      libraryModalOpen.value = false
    else if (shortcutsOpen.value)
      shortcutsOpen.value = false
    else if (documentDrawerOpen.value)
      documentDrawerOpen.value = false
  }

  return {
    screens,
    activeScreen,
    costExceeded,
    commandOpen,
    shortcutsOpen,
    libraryModalOpen,
    documentDrawerOpen,
    drawerPinned,
    citationPreview,
    commandQuery,
    commandItems,
    currentScreenTitle,
    mainNavigationItems,
    recentSessionItems,
    libraryStatItems,
    visibleToasts,
    setActiveScreen,
    pushToast,
    openCommand,
    openCreateLibrary,
    closeTopLayer,
  }
})
