<script setup lang="ts">
import { computed } from 'vue'
import { use } from 'echarts/core'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
import { storeToRefs } from 'pinia'
import { useWorkspaceNavigation } from '../../app/useWorkspaceNavigation'
import { useGraphStore } from '../../stores/graph'
import AppIcon from '../base/AppIcon.vue'
import { useCssChartPalette } from '../charts/useCssChartPalette'

use([CanvasRenderer, BarChart, GridComponent, TooltipComponent])

const graph = useGraphStore()
const palette = useCssChartPalette()
const { goToScreen } = useWorkspaceNavigation()
const { coOccurring, detailError, detailState, entityDetail, mentions } = storeToRefs(graph)

const mentionsOption = computed(() => ({
  animation: true,
  grid: { top: 2, right: 0, bottom: 2, left: 0 },
  tooltip: {
    trigger: 'axis',
    backgroundColor: palette.value.text,
    borderWidth: 0,
    textStyle: { color: palette.value.surface, fontFamily: 'JetBrains Mono', fontSize: 12 },
  },
  xAxis: { type: 'category', show: false, data: mentions.value.map((_, index) => index) },
  yAxis: { type: 'value', show: false },
  series: [
    {
      type: 'bar',
      data: mentions.value,
      barGap: 0,
      barWidth: 13,
      itemStyle: { color: palette.value.primary, opacity: 0.86 },
    },
  ],
}))

async function askInChat() {
  graph.citeNodeInChat()
  await goToScreen('chat')
}

function retryDetail() {
  if (graph.selectedEntityId)
    void graph.loadEntityDetail(graph.selectedEntityId)
}
</script>

<template>
  <aside class="kg-entity-drawer" aria-label="Entity detail">
    <header class="entity-drawer-head">
      <div class="drawer-title-row">
        <span class="entity-kind">{{ entityDetail?.kind }}</span>
        <div class="drawer-head-actions">
          <button type="button" @click="askInChat">
            <AppIcon name="chat" :size="16" />
            Ask in Chat
          </button>
          <button type="button" aria-label="Close entity detail" @click="graph.closeEntityDetail">
            <AppIcon name="close" :size="18" />
          </button>
        </div>
      </div>
      <h2>
        {{ graph.selectedNode }}
        <AppIcon name="star" :size="17" />
      </h2>
      <p>
        ID: {{ entityDetail?.stableId }}
        <AppIcon name="copy" :size="13" />
      </p>
    </header>

    <div v-if="detailState === 'loading'" class="entity-state" role="status">
      Loading entity details...
    </div>
    <div v-else-if="detailState === 'error'" class="entity-state is-error" role="alert">
      <strong>Unable to load entity.</strong>
      <span>{{ detailError }}</span>
      <button type="button" @click="retryDetail">Retry</button>
    </div>

    <nav v-else class="entity-tabs" aria-label="Entity detail tabs">
      <button class="active" type="button">Overview</button>
      <button type="button">Connections ({{ entityDetail?.connectionCountLabel }})</button>
      <button type="button">Evidence ({{ entityDetail?.evidenceCountLabel }})</button>
    </nav>

    <div v-if="detailState === 'success'" class="entity-drawer-body">
      <p class="entity-summary">
        {{ entityDetail?.summary }}
      </p>

      <section>
        <h3>Aliases</h3>
        <div class="alias-list">
          <span v-for="alias in entityDetail?.aliases" :key="alias">{{ alias }}</span>
          <span v-if="entityDetail?.hiddenAliasCountLabel" class="muted">{{ entityDetail.hiddenAliasCountLabel }}</span>
        </div>
      </section>

      <section>
        <h3>Network Statistics</h3>
        <dl class="network-stat-grid">
          <div v-for="stat in entityDetail?.stats" :key="stat.label">
            <dt>{{ stat.label }}</dt>
            <dd>{{ stat.value }}</dd>
          </div>
        </dl>
      </section>

      <section>
        <h3>Mentions Trend</h3>
        <VChart class="mentions-chart" :option="mentionsOption" autoresize />
        <div class="mentions-axis">
          <span>{{ entityDetail?.mentionsStartLabel }}</span>
          <span>{{ entityDetail?.mentionsEndLabel }}</span>
        </div>
      </section>

      <section>
        <h3>Co-occurring Entities</h3>
        <table class="co-entity-table">
          <tbody>
            <tr v-for="item in coOccurring" :key="item.name">
              <td><i :class="item.type" />{{ item.name }}</td>
              <td>{{ item.count }}</td>
            </tr>
          </tbody>
        </table>
      </section>
    </div>

    <footer v-if="detailState === 'success'" class="entity-drawer-footer">
      <button class="view-library-button" type="button">
        View in library
      </button>
      <button class="share-entity-button" type="button" aria-label="Share entity">
        <AppIcon name="share" :size="18" />
      </button>
    </footer>
  </aside>
</template>

<style scoped>
.kg-entity-drawer {
  display: flex;
  flex-direction: column;
  width: 380px;
  min-width: 380px;
  min-height: 0;
  border-left: 1px solid var(--color-outline-variant);
  background: var(--color-surface);
}

.entity-drawer-head {
  border-bottom: 1px solid var(--color-outline-variant);
  padding: 16px;
}

.drawer-title-row,
.drawer-head-actions,
.entity-drawer-footer {
  display: flex;
  align-items: center;
}

.drawer-title-row {
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 8px;
}

.entity-kind {
  border: 1px solid var(--color-alpha-primary-20);
  border-radius: var(--radius-xs);
  background: var(--color-alpha-primary-8);
  padding: 2px 8px;
  color: var(--color-primary);
  font-size: 11px;
  font-weight: 600;
  line-height: 16px;
  text-transform: uppercase;
}

.drawer-head-actions {
  gap: 8px;
}

.drawer-head-actions button {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  border: 0;
  border-radius: var(--radius-control);
  background: transparent;
  padding: 4px;
  color: var(--color-on-surface-variant);
}

.drawer-head-actions button:first-child {
  color: var(--color-primary);
  font-size: 13px;
  font-weight: 600;
}

.drawer-head-actions button:hover {
  background: var(--color-surface-container-high);
}

.entity-drawer-head h2 {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 0 4px;
  color: var(--color-on-surface);
  font-family: "Hanken Grotesk", Inter, sans-serif;
  font-size: 20px;
  font-weight: 600;
  letter-spacing: 0;
  line-height: 28px;
}

.entity-drawer-head h2 :deep(.app-icon),
.entity-drawer-head p :deep(.app-icon) {
  color: var(--color-outline);
}

.entity-drawer-head p {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin: 0;
  color: var(--color-outline);
  font-family: "JetBrains Mono", monospace;
  font-size: 12px;
  line-height: 16px;
}

.entity-tabs {
  display: flex;
  gap: 4px;
  border-bottom: 1px solid var(--color-outline-variant);
  padding: 8px 16px 0;
}

.entity-state {
  display: grid;
  place-items: center;
  min-height: 140px;
  gap: 8px;
  padding: 16px;
  color: var(--color-on-surface-variant);
  font-size: 13px;
  text-align: center;
}

.entity-state strong {
  color: var(--color-error);
}

.entity-state span {
  line-height: 20px;
}

.entity-state button {
  height: 32px;
  border: 1px solid var(--color-outline-variant);
  border-radius: var(--radius-control);
  background: var(--color-surface-container-lowest);
  padding: 0 14px;
  color: var(--color-primary);
  font-size: 13px;
  font-weight: 700;
}

.entity-tabs button {
  height: 36px;
  border: 0;
  border-bottom: 2px solid transparent;
  background: transparent;
  padding: 0 12px;
  color: var(--color-on-surface-variant);
  font-size: 13px;
}

.entity-tabs button.active {
  border-bottom-color: var(--color-primary);
  color: var(--color-primary);
  font-weight: 600;
}

.entity-drawer-body {
  display: grid;
  align-content: start;
  flex: 1 1 auto;
  min-height: 0;
  gap: 24px;
  overflow-y: auto;
  padding: 16px;
}

.entity-summary {
  margin: 0;
  color: var(--color-on-surface-variant);
  font-size: 13px;
  line-height: 20px;
}

.entity-drawer-body h3 {
  margin: 0 0 8px;
  color: var(--color-outline);
  font-size: 11px;
  font-weight: 600;
  line-height: 16px;
  text-transform: uppercase;
}

.alias-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.alias-list span {
  border: 1px solid var(--color-outline-variant);
  border-radius: var(--radius-xs);
  background: var(--color-surface-container);
  padding: 4px 8px;
  color: var(--color-on-surface-variant);
  font-family: "JetBrains Mono", monospace;
  font-size: 12px;
  line-height: 16px;
}

.alias-list span.muted {
  color: var(--color-outline);
}

.network-stat-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px 16px;
  margin: 0;
}

.network-stat-grid div {
  display: flex;
  justify-content: space-between;
  border-bottom: 1px solid var(--color-surface-variant);
  padding-bottom: 4px;
  font-size: 13px;
  line-height: 20px;
}

.network-stat-grid dt {
  color: var(--color-on-surface-variant);
}

.network-stat-grid dd {
  margin: 0;
  color: var(--color-on-surface);
  font-family: "JetBrains Mono", monospace;
}

.mentions-chart {
  height: 64px;
  min-height: 64px;
  border-radius: var(--radius-xs);
  background: var(--color-surface-variant);
}

.mentions-axis {
  display: flex;
  justify-content: space-between;
  margin-top: 4px;
  color: var(--color-outline);
  font-family: "JetBrains Mono", monospace;
  font-size: 12px;
  line-height: 16px;
}

.co-entity-table {
  width: 100%;
  border-collapse: collapse;
}

.co-entity-table tr + tr {
  border-top: 1px solid var(--color-alpha-outline-variant-72);
}

.co-entity-table td {
  padding: 6px 0;
  color: var(--color-on-surface);
  font-size: 13px;
  line-height: 20px;
}

.co-entity-table td:first-child {
  display: flex;
  align-items: center;
  gap: 6px;
}

.co-entity-table td:last-child {
  color: var(--color-outline);
  font-family: "JetBrains Mono", monospace;
  text-align: right;
}

.co-entity-table i {
  width: 8px;
  height: 8px;
  border-radius: var(--radius-indicator);
}

.co-entity-table .concept {
  background: var(--color-primary);
}

.co-entity-table .method {
  background: var(--color-secondary-container);
}

.entity-drawer-footer {
  flex: 0 0 auto;
  gap: 8px;
  border-top: 1px solid var(--color-outline-variant);
  padding: 16px;
}

.view-library-button,
.share-entity-button {
  height: 36px;
  border-radius: var(--radius-control);
}

.view-library-button {
  flex: 1 1 auto;
  border: 0;
  background: var(--color-primary);
  color: var(--color-on-primary);
  font-size: 13px;
  font-weight: 600;
}

.share-entity-button {
  display: grid;
  flex: 0 0 44px;
  place-items: center;
  border: 1px solid var(--color-outline-variant);
  background: var(--color-surface);
  color: var(--color-on-surface-variant);
}
</style>
