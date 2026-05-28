import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import {
  mainNavigation,
  screenNavigation,
  commandActionTemplates,
} from '../app/staticNavigation'
import {
  storageStat,
} from '../mocks/navigation'
import { useLibraryStore } from './library'
import { createSearchRepository } from '../services/search/searchRepository'
import type { ShellMetadata } from '../domain/search/types'
import type { CommandItem, ScreenId, ToastItem, ToastTone } from '../types/application'

const searchRepository = createSearchRepository()

export const useUiStore = defineStore('ui', () => {
  const library = useLibraryStore()
  const usesApiData = import.meta.env.VITE_DATA_SOURCE === 'api'
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
  const shellMetadata = ref<ShellMetadata | null>(null)
  const shellState = ref<'idle' | 'loading' | 'success' | 'error'>('idle')
  const shellError = ref<string | null>(null)
  const toastSeq = ref(1)
  const toasts = ref<ToastItem[]>([])

  const currentScreenTitle = computed(() => screens.find(item => item.id === activeScreen.value)?.label ?? 'Chat')
  const mainNavigationItems = computed(() => mainNavigation)
  const recentSessionItems = computed(() => shellMetadata.value?.recentSessions ?? [])
  const libraryStatItems = computed(() => shellMetadata.value?.libraryStats ?? [])
  const storageStatItem = computed(() => usesApiData ? null : storageStat)
  const shellProfileItem = computed(() => shellMetadata.value?.profile ?? null)
  const shellNotifications = computed(() => shellMetadata.value?.notifications ?? null)
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

  async function loadShellMetadata(libraryId = library.activeLibrary, force = false) {
    if (!libraryId)
      return

    if (!force && shellState.value === 'success')
      return

    shellState.value = 'loading'
    shellError.value = null

    try {
      shellMetadata.value = await searchRepository.getShellMetadata(libraryId)
      shellState.value = 'success'
    }
    catch (reason) {
      shellMetadata.value = null
      shellError.value = reason instanceof Error ? reason.message : 'Unable to load shell metadata.'
      shellState.value = 'error'
    }
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
    shellState,
    shellError,
    commandItems,
    currentScreenTitle,
    mainNavigationItems,
    recentSessionItems,
    libraryStatItems,
    storageStatItem,
    shellProfileItem,
    shellNotifications,
    visibleToasts,
    setActiveScreen,
    loadShellMetadata,
    pushToast,
    openCommand,
    openCreateLibrary,
    closeTopLayer,
  }
})
