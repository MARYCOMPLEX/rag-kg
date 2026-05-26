<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { useWorkspaceNavigation } from '../app/useWorkspaceNavigation'
import AppIcon from '../components/base/AppIcon.vue'
import GraphEntityDrawer from '../components/graph/GraphEntityDrawer.vue'
import { useGraphStore } from '../stores/graph'

const graph = useGraphStore()
const { entityTypes, selectedNode } = storeToRefs(graph)
const { goToScreen } = useWorkspaceNavigation()

async function citeNodeInChat() {
  graph.citeNodeInChat()
  await goToScreen('chat')
}
</script>

<template>
  <section class="kg-workspace">
    <aside class="kg-filter-panel" aria-label="Filters">
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
          <label v-for="type in entityTypes" :key="type.label" class="kg-filter-row">
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
            <b>&gt;= 0.65</b>
          </div>
          <input type="range" min="0" max="1" step="0.05" value="0.65">
        </section>
      </div>

      <footer>
        <button type="button">
          Apply filters
          <span>6</span>
        </button>
      </footer>
    </aside>

    <main class="kg-canvas-panel" role="application" aria-label="Knowledge graph for efficient-ml">
      <div class="kg-canvas-note top-note">Spec: Switch to WebGL when nodes &gt; 3000</div>
      <div class="kg-canvas-note bottom-note">Spec: Zoom &lt; 0.5 hides labels to declutter</div>

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
        <span>100%</span>
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
          <line x1="400" x2="250" y1="300" y2="150" />
          <line x1="400" x2="600" y1="300" y2="200" />
          <line x1="400" x2="200" y1="300" y2="400" />
          <line class="muted" x1="400" x2="550" y1="300" y2="450" />
        </g>

        <g class="kg-node selected" transform="translate(400, 300)" tabindex="0" @contextmenu.prevent="graph.openNodeContext" @click="selectedNode = 'GraphRAG'">
          <circle class="outer" r="44" />
          <circle class="inner" r="40" />
          <text y="5">GraphRAG</text>
        </g>
        <g class="kg-node concept" transform="translate(250, 150)" @click="selectedNode = 'Leiden algorithm'">
          <circle r="25" />
          <text y="40">Leiden algorithm</text>
        </g>
        <g class="kg-node method" transform="translate(600, 200)" @click="selectedNode = 'Community detection'">
          <circle class="outer" r="34" />
          <circle r="30" />
          <text y="45">Community detection</text>
        </g>
        <g class="kg-node dataset" transform="translate(200, 400)" @click="selectedNode = 'MultiHop-RAG'">
          <circle r="25" />
          <text y="40">MultiHop-RAG</text>
        </g>
        <g class="kg-node author faded" transform="translate(550, 450)" @click="selectedNode = 'D. Edge et al.'">
          <circle r="20" />
          <text y="35">D. Edge et al.</text>
        </g>
      </svg>

      <footer class="kg-canvas-footer">
        <span>8,491 entities | 31,219 triples</span>
        <span class="kg-legend"><i class="concept" /> Concept <i class="method" /> Method</span>
        <span>confidence &gt;= 0.65</span>
      </footer>
    </main>

    <GraphEntityDrawer />
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
