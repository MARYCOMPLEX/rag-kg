<script setup lang="ts">
import AppIcon from '../base/AppIcon.vue'
</script>

<template>
  <footer class="review-notice-bar">
    <p>
      <AppIcon name="warning" :size="15" />
      <span>NOTE (for designers): When 0 chunks match a subtopic, render a warning banner instead of inventing content.</span>
    </p>
    <p class="developer-note">
      <AppIcon name="info" :size="15" />
      <span>NOTE (for developers): Annotate unsubstantiated paragraph markers [?] and sync state via taskStore.</span>
    </p>
  </footer>
</template>

<style scoped>
.review-notice-bar {
  display: grid;
  flex: 0 0 auto;
  justify-items: center;
  gap: 4px;
  border-top: 1px solid var(--color-outline-variant);
  background: var(--color-surface-container-high);
  padding: 8px 16px;
  color: var(--color-on-surface-variant);
  font-size: 12px;
  line-height: 16px;
}

.review-notice-bar p {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0;
}

.review-notice-bar p:first-child :deep(.app-icon) {
  color: var(--color-tertiary-container);
}

.review-notice-bar .developer-note {
  color: var(--color-primary);
}
</style>
