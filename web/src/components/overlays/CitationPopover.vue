<script setup lang="ts">
import { computed } from 'vue'
import { storeToRefs } from 'pinia'
import { useChatStore } from '../../stores/chat'
import { useUiStore } from '../../stores/ui'

const ui = useUiStore()
const chat = useChatStore()
const { citationPreview } = storeToRefs(ui)
const { activeEvidence, evidenceList } = storeToRefs(chat)
const previewEvidence = computed(() => {
  return evidenceList.value.find(item => item.id === citationPreview.value) ?? activeEvidence.value
})
</script>

<template>
  <div v-if="citationPreview && previewEvidence" class="citation-popover">
    <strong>{{ previewEvidence.title }}</strong>
    <p>{{ previewEvidence.snippet }}</p>
    <small>{{ previewEvidence.meta }} / score {{ previewEvidence.score }}</small>
  </div>
</template>
