import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import type { CommandSearchOptions } from '../domain/search/types'
import type { CommandSearchResult } from '../types/application'
import { createSearchRepository } from '../services/search/searchRepository'

const searchRepository = createSearchRepository()

export const useSearchStore = defineStore('search', () => {
  const usesApiData = import.meta.env.VITE_DATA_SOURCE === 'api'
  const results = ref<CommandSearchResult[]>([])
  const state = ref<'idle' | 'loading' | 'success' | 'error'>('idle')
  const error = ref<string | null>(null)

  const entityResults = computed(() => results.value.filter(item => item.type === 'entity' || item.screen === 'graph'))
  const documentResults = computed(() => results.value.filter(item => item.type === 'document' || item.screen === 'docs'))

  async function search(libraryId: string, options: CommandSearchOptions) {
    if (!libraryId || (usesApiData && options.query.trim().length < 2)) {
      results.value = []
      state.value = 'success'
      error.value = null
      return
    }

    state.value = 'loading'
    error.value = null

    try {
      const response = await searchRepository.search(libraryId, options)
      results.value = response.results
      state.value = 'success'
    }
    catch (reason) {
      results.value = []
      error.value = reason instanceof Error ? reason.message : 'Unable to search this library.'
      state.value = 'error'
      throw reason
    }
  }

  return {
    results,
    state,
    error,
    entityResults,
    documentResults,
    search,
  }
})
