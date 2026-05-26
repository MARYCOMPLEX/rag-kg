import { onMounted, ref } from 'vue'

export function useCssChartPalette() {
  const palette = ref({
    primary: '',
    primarySoft: '',
    secondary: '',
    secondarySoft: '',
    success: '',
    danger: '',
    dangerSoft: '',
    surface: '',
    text: '',
    muted: '',
    border: '',
  })

  function readVariable(style: CSSStyleDeclaration, name: string) {
    return style.getPropertyValue(name).trim()
  }

  onMounted(() => {
    const style = getComputedStyle(document.documentElement)
    palette.value = {
      primary: readVariable(style, '--color-primary'),
      primarySoft: readVariable(style, '--color-primary-fixed'),
      secondary: readVariable(style, '--color-secondary'),
      secondarySoft: readVariable(style, '--color-secondary-container'),
      success: readVariable(style, '--color-success-700-exact'),
      danger: readVariable(style, '--color-danger-650-exact'),
      dangerSoft: readVariable(style, '--color-danger-50-exact'),
      surface: readVariable(style, '--color-surface-container-lowest'),
      text: readVariable(style, '--color-on-surface'),
      muted: readVariable(style, '--color-outline'),
      border: readVariable(style, '--color-outline-variant'),
    }
  })

  return palette
}
