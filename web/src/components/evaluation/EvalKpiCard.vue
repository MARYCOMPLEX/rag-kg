<script setup lang="ts">
import { computed } from 'vue'
import { use } from 'echarts/core'
import { GridComponent } from 'echarts/components'
import { LineChart } from 'echarts/charts'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
import AppIcon from '../base/AppIcon.vue'
import { useCssChartPalette } from '../charts/useCssChartPalette'

use([CanvasRenderer, GridComponent, LineChart])

const props = defineProps<{
  title: string
  value: string
  threshold: string
  tone: 'success' | 'secondary' | 'danger'
  points: number[]
  icon?: string
}>()

const palette = useCssChartPalette()

const chartOption = computed(() => {
  const color = props.tone === 'danger'
    ? palette.value.danger
    : props.tone === 'success'
      ? palette.value.success
      : palette.value.secondary

  return {
    animation: true,
    grid: { top: 2, right: 0, bottom: 2, left: 0 },
    xAxis: { type: 'category', show: false, data: props.points.map((_, index) => index) },
    yAxis: { type: 'value', show: false, min: 0, max: 1 },
    series: [
      {
        type: 'line',
        data: props.points,
        symbol: 'none',
        smooth: true,
        lineStyle: { width: 2, color },
        areaStyle: { color: props.tone === 'danger' ? palette.value.dangerSoft : palette.value.primarySoft, opacity: 0.42 },
      },
    ],
  }
})
</script>

<template>
  <section class="eval-kpi-card">
    <header>
      <span>{{ title }}</span>
      <AppIcon :name="icon ?? 'info'" :size="15" />
    </header>
    <div class="kpi-value-row">
      <strong>{{ value }}</strong>
      <span>{{ threshold }}</span>
    </div>
    <VChart class="kpi-spark-chart" :option="chartOption" autoresize />
  </section>
</template>

<style scoped>
.eval-kpi-card {
  display: flex;
  flex-direction: column;
  min-height: 132px;
  gap: 8px;
  overflow: hidden;
  border: 1px solid var(--color-outline-variant);
  border-radius: var(--radius-card);
  background: var(--color-surface-container-lowest);
  padding: 16px;
  transition: border-color var(--motion-duration-normal) var(--motion-ease-standard);
}

.eval-kpi-card:hover {
  border-color: var(--color-alpha-primary-container-42);
}

.eval-kpi-card header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  color: var(--color-on-surface-variant);
  font-size: 13px;
  font-weight: 500;
  line-height: 20px;
}

.eval-kpi-card header :deep(.app-icon) {
  color: var(--color-outline-variant);
}

.kpi-value-row {
  display: flex;
  align-items: baseline;
  gap: 4px;
  margin-top: 4px;
}

.kpi-value-row strong {
  color: var(--color-on-surface);
  font-family: "Hanken Grotesk", Inter, sans-serif;
  font-size: 32px;
  font-weight: 600;
  letter-spacing: 0;
  line-height: 40px;
}

.kpi-value-row span {
  color: var(--color-outline);
  font-family: "JetBrains Mono", monospace;
  font-size: 12px;
  line-height: 16px;
}

.kpi-spark-chart {
  height: 32px;
  min-height: 32px;
  margin-top: auto;
}
</style>
