import { nextTick, ref } from 'vue'

export function useDrawerScrollReset() {
  const drawerScrollAnchorRef = ref<HTMLElement | null>(null)

  function resetDrawerScroll() {
    void nextTick(() => {
      const drawerBody = drawerScrollAnchorRef.value?.closest<HTMLElement>('.el-drawer__body')
      if (drawerBody) drawerBody.scrollTop = 0
    })
  }

  return {
    drawerScrollAnchorRef,
    resetDrawerScroll,
  }
}
