<script setup lang="ts">
defineProps<{
  name: string
  size?: number
}>()
</script>

<template>
  <svg
    class="app-icon"
    :width="size ?? 18"
    :height="size ?? 18"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="1.8"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
  >
    <template v-if="name === 'chat'">
      <path d="M21 15a4 4 0 0 1-4 4H8l-5 3V7a4 4 0 0 1 4-4h10a4 4 0 0 1 4 4z" />
    </template>
    <template v-else-if="name === 'graph'">
      <circle cx="6" cy="6" r="2.5" /><circle cx="18" cy="7" r="2.5" /><circle cx="12" cy="18" r="2.5" />
      <path d="m8.3 7.3 7.4-.2M7.2 8.3l3.6 7.4M16.8 8.9l-3.6 6.8" />
    </template>
    <template v-else-if="name === 'upload'">
      <path d="M12 3v12" /><path d="m7 8 5-5 5 5" /><path d="M4 15v3a3 3 0 0 0 3 3h10a3 3 0 0 0 3-3v-3" />
    </template>
    <template v-else-if="name === 'library'">
      <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" /><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
    </template>
    <template v-else-if="name === 'dataset'">
      <ellipse cx="12" cy="5" rx="7" ry="3" /><path d="M5 5v6c0 1.7 3.1 3 7 3s7-1.3 7-3V5" /><path d="M5 11v6c0 1.7 3.1 3 7 3s7-1.3 7-3v-6" />
    </template>
    <template v-else-if="name === 'settings'">
      <circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.8 1.8 0 0 0 .36 2l.05.05a2.1 2.1 0 0 1-3 3l-.05-.05a1.8 1.8 0 0 0-2-.36 1.8 1.8 0 0 0-1.1 1.65V21a2.1 2.1 0 0 1-4.2 0v-.08A1.8 1.8 0 0 0 8 19.3a1.8 1.8 0 0 0-2 .36l-.05.05a2.1 2.1 0 0 1-3-3l.05-.05a1.8 1.8 0 0 0 .36-2 1.8 1.8 0 0 0-1.65-1.1H1.6a2.1 2.1 0 0 1 0-4.2h.08A1.8 1.8 0 0 0 3.3 8a1.8 1.8 0 0 0-.36-2l-.05-.05a2.1 2.1 0 0 1 3-3l.05.05A1.8 1.8 0 0 0 8 3.3a1.8 1.8 0 0 0 1.1-1.65V1.6a2.1 2.1 0 0 1 4.2 0v.08A1.8 1.8 0 0 0 15 3.3a1.8 1.8 0 0 0 2-.36l.05-.05a2.1 2.1 0 0 1 3 3l-.05.05A1.8 1.8 0 0 0 19.4 8c.2.6.8 1.1 1.65 1.1h.08a2.1 2.1 0 0 1 0 4.2h-.08A1.8 1.8 0 0 0 19.4 15z" />
    </template>
    <template v-else-if="name === 'review'">
      <path d="M9 11l2 2 4-5" /><path d="M20 6v12a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6" /><path d="M8 4h8" />
    </template>
    <template v-else-if="name === 'search'">
      <circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" />
    </template>
    <template v-else-if="name === 'bell'">
      <path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9" /><path d="M13.7 21a2 2 0 0 1-3.4 0" />
    </template>
    <template v-else-if="name === 'plus'">
      <path d="M12 5v14M5 12h14" />
    </template>
    <template v-else-if="name === 'file'">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><path d="M14 2v6h6" />
    </template>
    <template v-else-if="name === 'chevron'">
      <path d="m6 9 6 6 6-6" />
    </template>
    <template v-else-if="name === 'chart'">
      <path d="M4 19V5" /><path d="M4 19h16" /><path d="M8 16v-5M12 16V8M16 16v-8" />
    </template>
    <template v-else-if="name === 'help'">
      <circle cx="12" cy="12" r="9" /><path d="M9.2 9a3 3 0 0 1 5.6 1.5c0 2-2.8 2.2-2.8 4" /><path d="M12 18h.01" />
    </template>
    <template v-else-if="name === 'keyboard'">
      <rect x="3" y="6" width="18" height="12" rx="2" /><path d="M7 10h.01M11 10h.01M15 10h.01M19 10h.01M7 14h.01M11 14h5" />
    </template>
    <template v-else-if="name === 'reason'">
      <path d="M12 3a6 6 0 0 0-4 10.5V16h8v-2.5A6 6 0 0 0 12 3z" /><path d="M9 20h6M10 16v2h4v-2" />
    </template>
    <template v-else-if="name === 'send'">
      <path d="M22 2 11 13" /><path d="m22 2-7 20-4-9-9-4z" />
    </template>
    <template v-else-if="name === 'attach'">
      <path d="m21.4 11.6-8.5 8.5a6 6 0 0 1-8.5-8.5l9.2-9.2a4 4 0 0 1 5.7 5.7l-9.2 9.2a2 2 0 1 1-2.8-2.8l8.5-8.5" />
    </template>
    <template v-else-if="name === 'tools'">
      <path d="M14.7 6.3a4 4 0 0 0-5 5L3 18v3h3l6.7-6.7a4 4 0 0 0 5-5l-2.4 2.4-2.6-2.6z" />
    </template>
    <template v-else-if="name === 'close'">
      <path d="M18 6 6 18M6 6l12 12" />
    </template>
    <template v-else-if="name === 'menu'">
      <path d="M4 6h16M4 12h16M4 18h16" />
    </template>
    <template v-else-if="name === 'language'">
      <circle cx="12" cy="12" r="9" /><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18" />
    </template>
    <template v-else-if="name === 'briefcase'">
      <rect x="3" y="7" width="18" height="13" rx="2" /><path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M3 12h18" />
    </template>
    <template v-else-if="name === 'external'">
      <path d="M14 3h7v7" /><path d="M10 14 21 3" /><path d="M21 14v5a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5" />
    </template>
    <template v-else-if="name === 'check'">
      <path d="m5 12 4.5 4.5L19 7" />
    </template>
    <template v-else-if="name === 'pencil'">
      <path d="M12 20h9" /><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z" />
    </template>
    <template v-else-if="name === 'refresh'">
      <path d="M20 11a8 8 0 0 0-14.6-4.4L3 9" /><path d="M3 4v5h5" /><path d="M4 13a8 8 0 0 0 14.6 4.4L21 15" /><path d="M21 20v-5h-5" />
    </template>
    <template v-else-if="name === 'download'">
      <path d="M12 3v12" /><path d="m7 10 5 5 5-5" /><path d="M5 21h14" />
    </template>
    <template v-else-if="name === 'arrow-right'">
      <path d="M5 12h14" /><path d="m13 6 6 6-6 6" />
    </template>
    <template v-else-if="name === 'warning'">
      <path d="m12 3 10 18H2Z" /><path d="M12 9v5" /><path d="M12 18h.01" />
    </template>
    <template v-else-if="name === 'info'">
      <circle cx="12" cy="12" r="9" /><path d="M12 11v6" /><path d="M12 7h.01" />
    </template>
    <template v-else-if="name === 'timer'">
      <circle cx="12" cy="13" r="8" /><path d="M12 13 15 10" /><path d="M9 2h6" />
    </template>
    <template v-else-if="name === 'filter'">
      <path d="M4 5h16" /><path d="M7 12h10" /><path d="M10 19h4" />
    </template>
    <template v-else-if="name === 'calendar'">
      <rect x="4" y="5" width="16" height="15" rx="2" /><path d="M16 3v4M8 3v4M4 11h16" />
    </template>
    <template v-else-if="name === 'trash'">
      <path d="M3 6h18" /><path d="M8 6V4h8v2" /><path d="M19 6l-1 14H6L5 6" /><path d="M10 11v5M14 11v5" />
    </template>
    <template v-else-if="name === 'copy'">
      <rect x="9" y="9" width="11" height="11" rx="2" /><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
    </template>
    <template v-else-if="name === 'star'">
      <path d="m12 3 2.7 5.5 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.8 1-6.1-4.4-4.3 6.1-.9z" />
    </template>
    <template v-else-if="name === 'code'">
      <path d="m8 9-4 3 4 3" /><path d="m16 9 4 3-4 3" /><path d="m14 5-4 14" />
    </template>
    <template v-else-if="name === 'pin'">
      <path d="m14 4 6 6-4 1-4 4v4l-2 2-3-6-4-3 2-2h4l4-4z" />
    </template>
    <template v-else-if="name === 'share'">
      <path d="M4 12v7a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-7" /><path d="m16 6-4-4-4 4" /><path d="M12 2v14" />
    </template>
    <template v-else>
      <path d="M12 3 21 12 12 21 3 12z" />
    </template>
  </svg>
</template>
