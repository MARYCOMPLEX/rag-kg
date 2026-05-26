<script setup lang="ts">
import { storeToRefs } from 'pinia'
import BaseModal from '../base/BaseModal.vue'
import AppIcon from '../base/AppIcon.vue'
import { useUiStore } from '../../stores/ui'

const ui = useUiStore()
const { shortcutsOpen } = storeToRefs(ui)

const shortcutGroups = [
  {
    title: 'Global',
    items: [
      ['Cmd/Ctrl K', 'Open command palette'],
      ['/', 'Focus composer'],
      ['Esc', 'Close the top floating layer or stop streaming'],
      ['?', 'Open this shortcuts modal'],
    ],
  },
  {
    title: 'Navigation',
    items: [
      ['G then D', 'Jump to Documents'],
      ['G then C', 'Jump to Chat'],
      ['G then K', 'Jump to Knowledge Graph'],
      ['G then E', 'Jump to Evaluation'],
    ],
  },
  {
    title: 'Work surfaces',
    items: [
      ['KG + / - / 0', 'Zoom, fit, and reset canvas'],
      ['Table J / K / X', 'Move and select rows'],
      ['Cmd Enter', 'Send composer content'],
    ],
  },
]
</script>

<template>
  <BaseModal
    :show="shortcutsOpen"
    title="Keyboard shortcuts"
    subtitle="Fast paths for navigation, search, graph exploration, and data tables."
    size="md"
    close-label="Close shortcuts modal"
    @update:show="ui.shortcutsOpen = $event"
  >
    <template #icon>
      <span class="shortcut-modal-icon">
        <AppIcon name="keyboard" :size="20" />
      </span>
    </template>

    <div class="shortcut-groups">
      <section v-for="group in shortcutGroups" :key="group.title" class="shortcut-group">
        <h3>{{ group.title }}</h3>
        <dl>
          <template v-for="item in group.items" :key="item[0]">
            <dt><kbd>{{ item[0] }}</kbd></dt>
            <dd>{{ item[1] }}</dd>
          </template>
        </dl>
      </section>
    </div>

    <template #footer>
      <span class="shortcut-footer-note">Shortcuts are scoped to the active Library unless marked global.</span>
      <button class="shortcut-done-button" type="button" @click="ui.shortcutsOpen = false">
        Done
      </button>
    </template>
  </BaseModal>
</template>

<style scoped>
.shortcut-modal-icon {
  display: grid;
  place-items: center;
  width: 40px;
  height: 40px;
  border-radius: var(--radius-card);
  background: var(--color-primary-fixed);
  color: var(--color-primary);
}

.shortcut-groups {
  display: grid;
  gap: 20px;
}

.shortcut-group {
  display: grid;
  gap: 10px;
}

.shortcut-group h3 {
  margin: 0;
  color: var(--color-outline);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: .04em;
  line-height: 16px;
  text-transform: uppercase;
}

.shortcut-group dl {
  display: grid;
  grid-template-columns: minmax(132px, auto) minmax(0, 1fr);
  gap: 10px 20px;
  margin: 0;
}

.shortcut-group dt,
.shortcut-group dd {
  min-width: 0;
  margin: 0;
}

.shortcut-group kbd {
  display: inline-flex;
  align-items: center;
  min-height: 26px;
  border: 1px solid var(--color-outline-variant);
  border-radius: var(--radius-control);
  background: var(--color-surface-container-low);
  padding: 0 10px;
  color: var(--color-primary);
  font-family: "JetBrains Mono", monospace;
  font-size: 12px;
  font-weight: 700;
  line-height: 16px;
}

.shortcut-group dd {
  color: var(--color-on-surface);
  font-size: 14px;
  line-height: 26px;
}

.shortcut-footer-note {
  margin-right: auto;
  color: var(--color-outline);
  font-size: 12px;
  line-height: 16px;
}

.shortcut-done-button {
  height: 40px;
  border: 1px solid var(--color-primary-container);
  border-radius: var(--radius-control);
  background: var(--color-primary-container);
  padding: 0 18px;
  color: var(--color-on-primary);
  font-size: 14px;
  font-weight: 700;
}

@media (max-width: 620px) {
  .shortcut-group dl {
    grid-template-columns: 1fr;
  }

  .shortcut-group dd {
    line-height: 20px;
  }
}
</style>
