import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

export type ResponsiveDrawerLevel = 1 | 2 | 3

function visibleViewportWidth() {
  if (typeof window === 'undefined') return 720
  return window.visualViewport?.width || document.documentElement.clientWidth || window.innerWidth
}

export function computeResponsiveDrawerWidth(
  level: ResponsiveDrawerLevel = 1,
  viewportWidth = visibleViewportWidth(),
) {
  if (viewportWidth < 1024) {
    const totalGutter = viewportWidth < 480 ? 16 : 32
    return Math.max(0, Math.floor(viewportWidth - totalGutter))
  }
  if (level === 2) return Math.round(Math.min(820, Math.max(680, viewportWidth * 0.56)))
  if (level === 3) return Math.round(Math.min(680, Math.max(560, viewportWidth * 0.46)))
  return Math.round(Math.min(1080, Math.max(860, viewportWidth * 0.72)))
}

export function useResponsiveDrawerWidth(level: ResponsiveDrawerLevel = 1) {
  const drawerWidthPx = ref(computeResponsiveDrawerWidth(level))
  let resizeBound = false

  function updateDrawerWidth() {
    drawerWidthPx.value = computeResponsiveDrawerWidth(level)
  }

  function bindDrawerResize() {
    updateDrawerWidth()
    if (resizeBound || typeof window === 'undefined') return
    window.addEventListener('resize', updateDrawerWidth)
    window.visualViewport?.addEventListener('resize', updateDrawerWidth)
    resizeBound = true
  }

  function unbindDrawerResize() {
    if (!resizeBound || typeof window === 'undefined') return
    window.removeEventListener('resize', updateDrawerWidth)
    window.visualViewport?.removeEventListener('resize', updateDrawerWidth)
    resizeBound = false
  }

  onMounted(bindDrawerResize)
  onBeforeUnmount(unbindDrawerResize)

  return {
    drawerWidthPx,
    drawerSize: computed(() => `${drawerWidthPx.value}px`),
    updateDrawerWidth,
    bindDrawerResize,
    unbindDrawerResize,
  }
}
