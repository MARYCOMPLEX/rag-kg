<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { useWorkspaceNavigation } from '../../app/useWorkspaceNavigation'
import { useReviewStore } from '../../stores/review'

const review = useReviewStore()
const { reviewBackgrounded, reviewProgress } = storeToRefs(review)
const { goToScreen } = useWorkspaceNavigation()
</script>

<template>
  <button v-if="reviewBackgrounded" class="mini-pill" type="button" @click="goToScreen('review')">
    Review generation / {{ reviewProgress }}%
  </button>
</template>
