import { computed } from 'vue'
import { defineStore } from 'pinia'
import { documentSearchResults, entitySearchResults } from '../mocks/search'

export const useSearchStore = defineStore('search', () => {
  const entityResults = computed(() => entitySearchResults)
  const documentResults = computed(() => documentSearchResults)

  return {
    entityResults,
    documentResults,
  }
})
