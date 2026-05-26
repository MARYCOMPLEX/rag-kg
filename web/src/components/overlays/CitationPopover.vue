<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { useChatStore } from '../../stores/chat'
import { useUiStore } from '../../stores/ui'

const ui = useUiStore()
const chat = useChatStore()
const { citationPreview } = storeToRefs(ui)
const { activeEvidence } = storeToRefs(chat)
</script>

<template>
  <div v-if="citationPreview" class="citation-popover">
    <strong>{{ activeEvidence.title }}</strong>
    <p>{{ activeEvidence.snippet }}</p>
    <small>score {{ activeEvidence.score }} / safePolygon bridge / 240ms open</small>
  </div>
</template>
