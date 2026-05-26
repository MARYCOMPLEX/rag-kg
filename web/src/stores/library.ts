import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import type { CreateLibraryInput, LibrarySummary } from '../domain/libraries/types'
import { createLibraryRepository } from '../services/libraries/libraryRepository'

const libraryRepository = createLibraryRepository()

export const useLibraryStore = defineStore('libraries', () => {
  const activeLibrary = ref('graphrag-survey')
  const libraries = ref<LibrarySummary[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  const featuredLibraries = computed(() => libraries.value.filter(item => item.featured))

  async function loadLibraries(force = false) {
    if (!force && libraries.value.length)
      return

    loading.value = true
    error.value = null

    try {
      libraries.value = await libraryRepository.list()
    }
    catch (reason) {
      error.value = reason instanceof Error ? reason.message : 'Unable to load libraries.'
    }
    finally {
      loading.value = false
    }
  }

  async function createLibrary(input: CreateLibraryInput) {
    const result = await libraryRepository.create(input)
    libraries.value = [result.library, ...libraries.value.filter(item => item.id !== result.library.id)]
    activeLibrary.value = result.library.id
    return result
  }

  function selectLibrary(libraryId: string) {
    const nextLibrary = libraries.value.find(item => item.id === libraryId)
    if (!nextLibrary)
      return

    activeLibrary.value = nextLibrary.id
  }

  return {
    activeLibrary,
    libraries,
    featuredLibraries,
    loading,
    error,
    loadLibraries,
    createLibrary,
    selectLibrary,
  }
})
