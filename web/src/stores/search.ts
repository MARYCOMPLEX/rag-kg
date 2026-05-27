import { computed } from 'vue'
import { defineStore } from 'pinia'
import { documentSearchResults, entitySearchResults } from '../mocks/search'

export const useSearchStore = defineStore('search', () => {
  const usesApiData = import.meta.env.VITE_DATA_SOURCE === 'api'
  const entityResults = computed(() => usesApiData ? [] : entitySearchResults)
  const documentResults = computed(() => usesApiData ? [] : documentSearchResults)

  return {
    entityResults,
    documentResults,
  }
})
