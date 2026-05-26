<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { useWorkspaceNavigation } from '../../app/useWorkspaceNavigation'
import { useUiStore } from '../../stores/ui'
import type { NavEntry } from '../../types/application'
import AppIcon from '../base/AppIcon.vue'

const ui = useUiStore()
const { routeScreen, goToScreen } = useWorkspaceNavigation()
const { libraryStatItems, mainNavigationItems, recentSessionItems } = storeToRefs(ui)

function isNavActive(item: NavEntry) {
  return item.activeOn.includes(routeScreen.value)
}
</script>

<template>
  <aside class="side-nav" aria-label="Workspace navigation">
    <div class="side-nav-scroll">
      <nav class="nav-primary" aria-label="Main navigation">
        <button
          v-for="item in mainNavigationItems"
          :key="item.key"
          class="nav-item"
          :class="{ active: isNavActive(item) }"
          type="button"
          @click="goToScreen(item.id)"
        >
          <AppIcon :name="item.icon" :size="20" />
          <span>{{ item.label }}</span>
        </button>
      </nav>

      <section class="recent-sessions" aria-label="Recent sessions">
        <h3>Recent Sessions</h3>
        <button
          v-for="session in recentSessionItems"
          :key="session.title"
          class="recent-session"
          :class="{ active: session.active }"
          type="button"
        >
          <span>{{ session.title }}</span>
          <b>{{ session.time }}</b>
        </button>
      </section>

      <section class="chat-stats-card" aria-label="Library statistics">
        <h3>Library Stats</h3>
        <div v-for="stat in libraryStatItems" :key="stat.label">
          <span>{{ stat.label }}</span>
          <b>{{ stat.value }}</b>
        </div>
        <p>
          <span>Storage</span>
          <b>482 GB</b>
        </p>
      </section>
    </div>

    <div class="chat-side-bottom">
      <button class="nav-item subtle" type="button" @click="goToScreen('eval')">
        <AppIcon name="settings" :size="20" />
        <span>Settings</span>
      </button>
      <div class="profile-row">
        <span>RL</span>
        <div>
          <strong>RL Research Lab Admin</strong>
          <small>Premium Plan</small>
        </div>
      </div>
    </div>
  </aside>
</template>
