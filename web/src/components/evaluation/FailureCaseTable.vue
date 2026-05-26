<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { useWorkspaceNavigation } from '../../app/useWorkspaceNavigation'
import { useEvaluationStore } from '../../stores/evaluation'
import AppIcon from '../base/AppIcon.vue'

const { goToScreen } = useWorkspaceNavigation()
const evaluation = useEvaluationStore()
const { failureCases } = storeToRefs(evaluation)
</script>

<template>
  <section class="failure-table-panel">
    <header>
      <div>
        <h2>Top failure cases</h2>
        <span>Sample: Bottom 5% EM@1</span>
      </div>
      <button type="button">
        View all
        <AppIcon name="arrow-right" :size="15" />
      </button>
    </header>
    <div class="failure-table-scroll">
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Dataset</th>
            <th>Question</th>
            <th>Failure type</th>
            <th>EM@1</th>
            <th>Faithfulness</th>
            <th>C@1</th>
            <th>Latency</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in failureCases" :key="row.id">
            <td class="id-cell">{{ row.id }}</td>
            <td>{{ row.dataset }}</td>
            <td class="question-cell">{{ row.question }}</td>
            <td><span class="failure-chip" :class="row.tone">{{ row.failure }}</span></td>
            <td class="metric-cell danger">{{ row.em }}</td>
            <td class="metric-cell danger">{{ row.faithfulness }}</td>
            <td class="metric-cell">{{ row.citation }}</td>
            <td class="metric-cell">{{ row.latency }}</td>
            <td>
              <button class="replay-button" type="button" @click="goToScreen('chat')">
                <AppIcon name="refresh" :size="14" />
                Replay
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<style scoped>
.failure-table-panel {
  overflow: hidden;
  border: 1px solid var(--color-outline-variant);
  border-radius: var(--radius-card);
  background: var(--color-surface-container-lowest);
}

.failure-table-panel header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  border-bottom: 1px solid var(--color-outline-variant);
  background: var(--color-alpha-primary-fixed-26);
  padding: 16px;
}

.failure-table-panel header div {
  display: flex;
  align-items: center;
  gap: 16px;
}

.failure-table-panel h2 {
  margin: 0;
  color: var(--color-on-surface);
  font-size: 14px;
  font-weight: 600;
  line-height: 22px;
}

.failure-table-panel header span {
  border: 1px solid var(--color-alpha-outline-variant-72);
  border-radius: var(--radius-control);
  background: var(--color-surface);
  padding: 2px 8px;
  color: var(--color-outline);
  font-size: 11px;
  font-weight: 600;
  line-height: 16px;
  text-transform: uppercase;
}

.failure-table-panel header button {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  border: 0;
  background: transparent;
  color: var(--color-primary);
  font-size: 13px;
  font-weight: 500;
}

.failure-table-scroll {
  overflow-x: auto;
}

table {
  width: 100%;
  min-width: 900px;
  border-collapse: collapse;
  text-align: left;
}

thead tr {
  border-bottom: 1px solid var(--color-outline-variant);
  background: var(--color-alpha-primary-fixed-26);
  color: var(--color-on-surface-variant);
  font-size: 11px;
  font-weight: 600;
  line-height: 16px;
  text-transform: uppercase;
}

th,
td {
  padding: 10px 16px;
}

tbody tr {
  border-bottom: 1px solid var(--color-alpha-outline-variant-72);
  color: var(--color-on-surface);
  font-size: 13px;
  line-height: 20px;
  transition: background var(--motion-duration-normal) var(--motion-ease-standard);
}

tbody tr:hover {
  background: var(--color-surface-container-low);
}

.id-cell,
.metric-cell {
  font-family: "JetBrains Mono", monospace;
}

.id-cell {
  color: var(--color-primary);
}

.question-cell {
  max-width: 260px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.metric-cell {
  text-align: right;
}

.metric-cell.danger {
  color: var(--color-error);
}

.failure-chip {
  display: inline-flex;
  align-items: center;
  border-radius: var(--radius-control);
  padding: 2px 8px;
  font-size: 11px;
  font-weight: 500;
  line-height: 16px;
}

.failure-chip.danger,
.failure-chip.warning {
  border: 1px solid var(--color-alpha-danger-20);
  background: var(--color-danger-50-exact);
  color: var(--color-danger-650-exact);
}

.failure-chip.neutral {
  border: 1px solid var(--color-outline-variant);
  background: var(--color-surface-container-low);
  color: var(--color-on-surface-variant);
}

.replay-button {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  border: 0;
  border-radius: var(--radius-control);
  background: var(--color-surface-container);
  padding: 4px 8px;
  color: var(--color-outline);
  font-size: 11px;
  font-weight: 500;
  opacity: 0;
  transition:
    opacity var(--motion-duration-normal) var(--motion-ease-standard),
    color var(--motion-duration-normal) var(--motion-ease-standard);
}

tbody tr:hover .replay-button,
.replay-button:focus-visible {
  opacity: 1;
}

.replay-button:hover {
  color: var(--color-primary);
}
</style>
