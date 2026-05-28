<script setup lang="ts">
import { computed, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useRoute } from 'vue-router'
import { useWorkspaceNavigation } from '../app/useWorkspaceNavigation'
import AppIcon from '../components/base/AppIcon.vue'
import GraphEntityDrawer from '../components/graph/GraphEntityDrawer.vue'
import { useGraphStore } from '../stores/graph'

const route = useRoute()
const graph = useGraphStore()
const { canvas, entityTypes, selectedEntityId, workspaceError, workspaceState } = storeToRefs(graph)
const { goToScreen } = useWorkspaceNavigation()
const libraryId = computed(() => String(route.params.libraryId ?? ''))

watch(libraryId, (nextLibraryId) => {
  void graph.loadWorkspace(nextLibraryId, true)
}, { immediate: true })

async function citeNodeInChat() {
  graph.citeNodeInChat()
  await goToScreen('chat')
}

function reloadGraph() {
  void graph.loadWorkspace(libraryId.value, true)
}
</script>

<template>
  <section class="kg-workspace">
    <div v-if="workspaceState === 'loading'" class="kg-pending-state" role="status">
      <AppIcon name="graph" :size="28" />
      <h1>Loading graph workspace</h1>
      <p>Fetching graph filters, canvas data, and summary labels from this library.</p>
    </div>

    <div v-else-if="workspaceState === 'error'" class="kg-pending-state is-error" role="alert">
      <AppIcon name="warning" :size="28" />
      <h1>Unable to load graph</h1>
      <p>{{ workspaceError }}</p>
      <button type="button" @click="reloadGraph">Retry</button>
    </div>

    <div v-else-if="canvas && canvas.nodes.length === 0" class="kg-pending-state" role="status">
      <AppIcon name="graph" :size="28" />
      <h1>No graph data yet</h1>
      <p>{{ canvas.summaryLabel }} / {{ canvas.confidenceLabel }}. Upload and index documents to populate the knowledge graph.</p>
    </div>

    <aside v-else-if="canvas" class="kg-filter-panel" aria-label="Filters">
      <header>
        <h2>Filters</h2>
        <div>
          <button type="button">Reset</button>
          <button type="button" aria-label="Refresh filters">
            <AppIcon name="refresh" :size="16" />
          </button>
        </div>
      </header>

      <div class="kg-filter-body">
        <section>
          <h3>Entity Types</h3>
          <label v-for="type in entityTypes" :key="type.key ?? type.label" class="kg-filter-row">
            <span>
              <input :checked="type.checked" type="checkbox">
              <i :class="type.tone" />
              {{ type.label }}
            </span>
            <b>{{ type.count }}</b>
          </label>
        </section>

        <section class="confidence-filter">
          <div>
            <h3>Confidence</h3>
            <b>{{ canvas.confidenceLabel }}</b>
          </div>
          <input type="range" min="0" max="1" step="0.05" :value="graph.workspace?.filters.minConfidence ?? 0">
        </section>
      </div>

      <footer>
        <button type="button">
          Apply filters
          <span>{{ canvas?.filterCountLabel }}</span>
        </button>
      </footer>
    </aside>

    <main v-if="canvas && canvas.nodes.length" class="kg-canvas-panel" role="application" aria-label="Knowledge graph">
      <div class="kg-canvas-note top-note">{{ canvas?.topNote }}</div>
      <div class="kg-canvas-note bottom-note">{{ canvas?.bottomNote }}</div>

      <div class="kg-toolbar" aria-label="Canvas toolbar">
        <button type="button" title="Fit to view">
          <AppIcon name="search" :size="18" />
        </button>
        <button type="button" title="Reset view">
          <AppIcon name="refresh" :size="18" />
        </button>
        <button type="button" title="Export">
          <AppIcon name="download" :size="18" />
        </button>
        <button type="button" title="Cypher Query">
          <AppIcon name="code" :size="18" />
        </button>
        <span>{{ canvas?.zoomLabel }}</span>
      </div>

      <div v-if="graph.contextMenuOpen" class="kg-context-menu" :style="{ left: `${graph.contextMenuX - 260}px`, top: `${graph.contextMenuY - 56}px` }">
        <button type="button"><AppIcon name="plus" :size="15" />Expand 1-hop</button>
        <button type="button"><AppIcon name="close" :size="15" />Hide</button>
        <button type="button"><AppIcon name="pin" :size="15" />Pin</button>
        <span />
        <button type="button"><AppIcon name="copy" :size="15" />Copy ID</button>
        <button type="button" class="primary" @click="citeNodeInChat"><AppIcon name="chat" :size="15" />Cite in Chat</button>
      </div>

      <svg class="kg-svg" viewBox="0 0 800 600" aria-hidden="true">
        <defs>
          <marker id="arrowhead" markerHeight="7" markerWidth="10" orient="auto" refX="20" refY="3.5">
            <polygon fill="var(--color-outline-variant)" points="0 0, 10 3.5, 0 7" />
          </marker>
        </defs>
        <g class="kg-edges" marker-end="url(#arrowhead)">
          <line
            v-for="edge in canvas?.edges"
            :key="edge.id"
            :class="{ muted: edge.muted }"
            :x1="edge.x1"
            :x2="edge.x2"
            :y1="edge.y1"
            :y2="edge.y2"
          />
        </g>

        <g
          v-for="node in canvas?.nodes"
          :key="node.id"
          class="kg-node"
          :class="[node.tone, { selected: node.selected, faded: node.faded }]"
          :transform="`translate(${node.x}, ${node.y})`"
          tabindex="0"
          @contextmenu.prevent="graph.openNodeContext"
          @click="graph.selectNode(node.id)"
        >
          <circle v-if="node.outerRadius" class="outer" :r="node.outerRadius" />
          <circle :class="{ inner: node.selected }" :r="node.radius" />
          <text :y="node.selected ? 5 : node.radius + 15">{{ node.label }}</text>
        </g>
      </svg>

      <footer class="kg-canvas-footer">
        <span>{{ canvas?.summaryLabel }}</span>
        <span class="kg-legend">
          <template v-for="item in canvas?.legendItems" :key="item.label">
            <i :class="item.tone" /> {{ item.label }}
          </template>
        </span>
        <span>{{ canvas?.confidenceLabel }}</span>
      </footer>
    </main>

    <GraphEntityDrawer v-if="selectedEntityId && canvas?.nodes.length" />
  </section>
</template>

<style scoped>
.kg-workspace {
  display: grid;
  grid-template-columns: 280px minmax(360px, 1fr) 380px;
  width: 100%;
  height: 100%;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  background: var(--color-surface);
}

.kg-pending-state {
  display: grid;
  grid-column: 1 / -1;
  place-items: center;
  align-content: center;
  gap: 12px;
  margin: 24px;
  border: 1px dashed var(--color-outline-variant);
  border-radius: var(--radius-card);
  background: var(--color-surface-container-lowest);
  padding: 32px;
  color: var(--color-on-surface-variant);
  text-align: center;
}

.kg-pending-state :deep(.app-icon) {
  color: var(--color-primary);
}

.kg-pending-state h1 {
  margin: 0;
  color: var(--color-on-surface);
  font-size: 20px;
  line-height: 28px;
}

.kg-pending-state p {
  max-width: 760px;
  margin: 0;
  line-height: 22px;
}

.kg-pending-state code {
  color: var(--color-on-surface);
  font-size: .92em;
}

.kg-pending-state.is-error :deep(.app-icon),
.kg-pending-state.is-error h1 {
  color: var(--color-error);
}

.kg-pending-state button {
  height: 34px;
  border: 1px solid var(--color-outline-variant);
  border-radius: var(--radius-control);
  background: var(--color-surface-container-lowest);
  padding: 0 14px;
  color: var(--color-primary);
  font-size: 13px;
  font-weight: 700;
}

.kg-filter-panel {
  display: flex;
  flex-direction: column;
  min-height: 0;
  border-right: 1px solid var(--color-outline-variant);
  background: var(--color-surface);
}

.kg-filter-panel header,
.kg-filter-panel footer {
  flex: 0 0 auto;
  border-color: var(--color-outline-variant);
}

.kg-filter-panel header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--color-outline-variant);
  padding: 16px;
}

.kg-filter-panel h2 {
  margin: 0;
  color: var(--color-on-surface);
  font-family: "Hanken Grotesk", Inter, sans-serif;
  font-size: 14px;
  font-weight: 700;
  line-height: 22px;
}

.kg-filter-panel header div {
  display: flex;
  align-items: center;
  gap: 8px;
}

.kg-filter-panel header button {
  border: 0;
  background: transparent;
  color: var(--color-on-surface-variant);
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
}

.kg-filter-body {
  display: grid;
  align-content: start;
  flex: 1 1 auto;
  min-height: 0;
  gap: 24px;
  overflow-y: auto;
  padding: 16px;
}

.kg-filter-body h3 {
  margin: 0 0 8px;
  color: var(--color-on-surface-variant);
  font-size: 11px;
  font-weight: 600;
  line-height: 16px;
  text-transform: uppercase;
}

.kg-filter-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-top: 8px;
  color: var(--color-on-surface);
  font-size: 13px;
  line-height: 20px;
}

.kg-filter-row span {
  display: inline-flex;
  align-items: center;
  min-width: 0;
  gap: 8px;
}

.kg-filter-row input {
  width: 16px;
  height: 16px;
  accent-color: var(--color-primary);
}

.kg-filter-row i,
.kg-legend i {
  width: 8px;
  height: 8px;
  border-radius: var(--radius-indicator);
}

.kg-filter-row b {
  color: var(--color-outline);
  font-family: "JetBrains Mono", monospace;
  font-size: 12px;
  font-weight: 450;
}

.concept {
  background: var(--color-primary);
}

.method {
  background: var(--color-secondary-container);
}

.dataset {
  background: var(--color-warning-750-exact);
}

.metric {
  background: var(--color-kg-author);
}

.author {
  background: var(--color-success-625-exact);
}

.venue {
  background: var(--color-danger-500-exact);
}

.confidence-filter div {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.confidence-filter b {
  color: var(--color-on-surface);
  font-family: "JetBrains Mono", monospace;
  font-size: 12px;
}

.confidence-filter input {
  width: 100%;
  accent-color: var(--color-primary);
}

.kg-filter-panel footer {
  border-top: 1px solid var(--color-outline-variant);
  padding: 16px;
}

.kg-filter-panel footer button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 36px;
  gap: 8px;
  border: 0;
  border-radius: var(--radius-control);
  background: var(--color-primary);
  color: var(--color-on-primary);
  font-size: 13px;
  font-weight: 600;
}

.kg-filter-panel footer span {
  border-radius: var(--radius-indicator);
  background: var(--color-alpha-white-22);
  padding: 2px 6px;
  font-size: 10px;
}

.kg-canvas-panel {
  position: relative;
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  background:
    radial-gradient(circle, var(--color-outline-variant) 1px, transparent 1px),
    var(--color-surface-container-lowest);
  background-size: 20px 20px;
}

.kg-toolbar {
  position: absolute;
  top: 16px;
  left: 50%;
  z-index: var(--z-local);
  display: flex;
  align-items: center;
  transform: translateX(-50%);
  border: 1px solid var(--color-outline-variant);
  border-radius: var(--radius-control);
  background: var(--color-surface);
  padding: 4px;
  box-shadow: var(--shadow-xs);
}

.kg-toolbar button {
  display: grid;
  place-items: center;
  width: 30px;
  height: 30px;
  border: 0;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--color-on-surface-variant);
}

.kg-toolbar button:hover {
  background: var(--color-surface-container-high);
  color: var(--color-primary);
}

.kg-toolbar button + button,
.kg-toolbar span {
  border-left: 1px solid var(--color-outline-variant);
}

.kg-toolbar span {
  padding: 0 8px;
  color: var(--color-on-surface-variant);
  font-family: "JetBrains Mono", monospace;
  font-size: 12px;
}

.kg-canvas-note {
  position: absolute;
  z-index: var(--z-raised);
  background: var(--color-warning-50-exact);
  color: var(--color-on-surface);
  font-family: "JetBrains Mono", monospace;
  font-size: 10px;
  line-height: 14px;
}

.top-note {
  top: 14px;
  left: 14px;
}

.bottom-note {
  bottom: 40px;
  left: 14px;
}

.kg-context-menu {
  position: absolute;
  z-index: var(--z-dropdown);
  width: 192px;
  border: 1px solid var(--color-outline-variant);
  border-radius: var(--radius-control);
  background: var(--color-surface);
  padding: 4px 0;
  box-shadow: var(--shadow-lg);
}

.kg-context-menu button {
  display: flex;
  align-items: center;
  width: 100%;
  height: 32px;
  gap: 8px;
  border: 0;
  background: transparent;
  padding: 0 12px;
  color: var(--color-on-surface);
  font-size: 13px;
  text-align: left;
}

.kg-context-menu button:hover {
  background: var(--color-surface-container-high);
}

.kg-context-menu button.primary {
  color: var(--color-primary);
}

.kg-context-menu span {
  display: block;
  height: 1px;
  margin: 4px 0;
  background: var(--color-outline-variant);
}

.kg-svg {
  flex: 1 1 auto;
  width: 100%;
  height: 100%;
}

.kg-edges line {
  stroke: var(--color-outline-variant);
  stroke-width: 1.5;
}

.kg-edges line.muted {
  opacity: .3;
}

.kg-node {
  cursor: pointer;
  transition: transform var(--motion-duration-spring) var(--motion-ease-spring);
}

.kg-node circle {
  fill: var(--color-surface-container);
  stroke-width: 2;
}

.kg-node text {
  fill: var(--color-on-surface-variant);
  font-family: Inter, sans-serif;
  font-size: 10px;
  text-anchor: middle;
}

.kg-node.selected .outer {
  fill: none;
  stroke: var(--color-primary);
  stroke-width: 2;
}

.kg-node.selected .inner {
  fill: var(--color-surface-container);
  stroke: var(--color-primary);
  stroke-width: 3;
}

.kg-node.selected text {
  fill: var(--color-on-surface);
  font-size: 12px;
  font-weight: 600;
}

.kg-node.concept circle {
  stroke: var(--color-primary);
}

.kg-node.method .outer {
  fill: none;
  stroke: var(--color-secondary-fixed-dim);
  stroke-width: 1.5;
}

.kg-node.method circle:not(.outer) {
  stroke: var(--color-secondary-container);
}

.kg-node.dataset circle {
  stroke: var(--color-warning-750-exact);
  stroke-dasharray: 4 2;
}

.kg-node.author circle {
  stroke: var(--color-success-625-exact);
}

.kg-node.faded {
  opacity: .3;
}

.kg-canvas-footer {
  position: absolute;
  right: 0;
  bottom: 0;
  left: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  border-top: 1px solid var(--color-outline-variant);
  background: var(--color-alpha-surface-82);
  backdrop-filter: blur(12px);
  padding: 8px;
  color: var(--color-outline);
  font-family: "JetBrains Mono", monospace;
  font-size: 12px;
  line-height: 16px;
}

.kg-legend {
  display: flex;
  align-items: center;
  gap: 6px;
}

@media (max-width: 1180px) {
  .kg-workspace {
    grid-template-columns: 240px minmax(300px, 1fr) 340px;
  }

  :deep(.kg-entity-drawer) {
    width: 340px;
    min-width: 340px;
  }
}
</style>
