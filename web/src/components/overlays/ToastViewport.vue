<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { useUiStore } from '../../stores/ui'

const ui = useUiStore()
const { visibleToasts } = storeToRefs(ui)
</script>

<template>
  <div class="toast-viewport">
    <article v-for="toast in visibleToasts" :key="toast.id" class="toast" :class="toast.tone">
      <strong>{{ toast.title }}</strong>
      <p>{{ toast.detail }}</p>
      <button v-if="toast.action" type="button">
        {{ toast.action }}
      </button>
    </article>
  </div>
</template>
