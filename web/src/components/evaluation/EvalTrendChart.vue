<script setup lang="ts">
import { computed } from 'vue'
import { use } from 'echarts/core'
import { BarChart } from 'echarts/charts'
import { DataZoomComponent, GridComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
import { storeToRefs } from 'pinia'
import AppIcon from '../base/AppIcon.vue'
import { useEvaluationStore } from '../../stores/evaluation'
import { useCssChartPalette } from '../charts/useCssChartPalette'

use([CanvasRenderer, BarChart, GridComponent, TooltipComponent, DataZoomComponent])

const palette = useCssChartPalette()
const evaluation = useEvaluationStore()
const { trend, trendLegend } = storeToRefs(evaluation)

const option = computed(() => ({
  animation: true,
  color: [palette.value.success, palette.value.secondary, palette.value.secondarySoft, palette.value.danger],
  tooltip: {
    trigger: 'axis',
    axisPointer: { type: 'shadow' },
    backgroundColor: palette.value.text,
    borderWidth: 0,
    textStyle: { color: palette.value.surface, fontSize: 12, fontFamily: 'JetBrains Mono' },
  },
  grid: { top: 12, right: 8, bottom: 30, left: 34 },
  xAxis: {
    type: 'category',
    data: trend.value.days,
    axisTick: { show: false },
    axisLine: { lineStyle: { color: palette.value.border } },
    axisLabel: { color: palette.value.muted, fontSize: 10, interval: 8, fontFamily: 'JetBrains Mono' },
  },
  yAxis: {
    type: 'value',
    min: 0,
    max: 1,
    splitNumber: 4,
    axisLabel: { color: palette.value.muted, fontSize: 10, fontFamily: 'JetBrains Mono' },
    splitLine: { lineStyle: { color: palette.value.border, opacity: 0.38 } },
  },
  dataZoom: [
    { type: 'inside', start: 20, end: 72 },
    {
      type: 'slider',
      start: 20,
      end: 72,
      height: 16,
      bottom: 0,
      borderColor: palette.value.border,
      fillerColor: palette.value.primarySoft,
      handleSize: 12,
      showDetail: false,
      brushSelect: false,
    },
  ],
  series: [
    { name: 'EM@1', type: 'bar', barWidth: 3, data: trend.value.em },
    { name: 'Faithfulness', type: 'bar', barWidth: 3, data: trend.value.faithfulness },
    { name: 'C@1', type: 'bar', barWidth: 3, data: trend.value.citation },
    { name: 'Latency p95', type: 'bar', barWidth: 3, data: trend.value.latency },
  ],
}))
</script>

<template>
  <section class="eval-trend-card">
    <header class="trend-card-head">
      <h2>Trend (daily)</h2>
      <div class="trend-controls">
        <div class="trend-legend" aria-label="Chart legend">
          <span v-for="item in trendLegend" :key="item.label">
            <i :class="item.tone" />
            {{ item.label }}
          </span>
        </div>
        <div class="trend-range">
          <button type="button">7D</button>
          <button class="active" type="button">30D</button>
          <button type="button">90D</button>
        </div>
        <button class="trend-icon-button" type="button" aria-label="Select date range">
          <AppIcon name="calendar" :size="16" />
        </button>
      </div>
    </header>
    <VChart class="trend-chart" :option="option" autoresize />
  </section>
</template>

<style scoped>
.eval-trend-card {
  display: flex;
  flex: 2 1 0;
  flex-direction: column;
  min-width: 0;
  min-height: 364px;
  border: 1px solid var(--color-outline-variant);
  border-radius: var(--radius-card);
  background: var(--color-surface-container-lowest);
  padding: 16px;
}

.trend-card-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 24px;
}

.trend-card-head h2 {
  margin: 0;
  color: var(--color-on-surface);
  font-size: 14px;
  font-weight: 600;
  line-height: 22px;
}

.trend-controls {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

.trend-legend,
.trend-range {
  display: flex;
  align-items: center;
  border: 1px solid var(--color-alpha-outline-variant-72);
  border-radius: var(--radius-control);
  background: var(--color-surface-container-low);
}

.trend-legend {
  gap: 8px;
  padding: 4px 8px;
}

.trend-legend span {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: var(--color-on-surface-variant);
  font-size: 11px;
  font-weight: 600;
  line-height: 16px;
  text-transform: uppercase;
}

.trend-legend i {
  width: 8px;
  height: 8px;
  border-radius: var(--radius-indicator);
}

.trend-legend .success {
  background: var(--color-success-700-exact);
}

.trend-legend .secondary {
  background: var(--color-secondary);
}

.trend-legend .citation {
  border: 1px solid var(--color-secondary);
  background: var(--color-secondary-container);
}

.trend-legend .danger {
  background: var(--color-danger-650-exact);
}

.trend-range {
  padding: 2px;
}

.trend-range button,
.trend-icon-button {
  border: 0;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--color-on-surface-variant);
  font-size: 11px;
  font-weight: 600;
  line-height: 16px;
}

.trend-range button {
  min-width: 40px;
  height: 28px;
}

.trend-range button.active {
  border: 1px solid var(--color-alpha-outline-variant-72);
  background: var(--color-surface-container-lowest);
  color: var(--color-on-surface);
  box-shadow: var(--shadow-xs);
}

.trend-icon-button {
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  border: 1px solid var(--color-outline-variant);
  background: var(--color-surface-container-lowest);
}

.trend-chart {
  flex: 1 1 auto;
  min-height: 264px;
}
</style>
