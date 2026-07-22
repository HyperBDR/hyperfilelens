import { onBeforeUnmount, onMounted, ref } from 'vue'

export const PHONE_MEDIA_QUERY = '(max-width: 767.98px)'
export const TABLET_MEDIA_QUERY = '(min-width: 768px) and (max-width: 1023.98px)'
export const DESKTOP_MEDIA_QUERY = '(min-width: 1024px)'
export const TOUCH_LIKE_MEDIA_QUERY = '(hover: none), (pointer: coarse)'

function mediaMatches(query: string, fallback: boolean) {
  return typeof window === 'undefined' ? fallback : window.matchMedia(query).matches
}

export function useResponsiveLayout() {
  const isPhone = ref(mediaMatches(PHONE_MEDIA_QUERY, false))
  const isTablet = ref(mediaMatches(TABLET_MEDIA_QUERY, false))
  const isDesktop = ref(mediaMatches(DESKTOP_MEDIA_QUERY, true))
  const isTouchLike = ref(mediaMatches(TOUCH_LIKE_MEDIA_QUERY, false))
  const mediaQueries: MediaQueryList[] = []

  function update() {
    if (typeof window === 'undefined') return
    isPhone.value = window.matchMedia(PHONE_MEDIA_QUERY).matches
    isTablet.value = window.matchMedia(TABLET_MEDIA_QUERY).matches
    isDesktop.value = window.matchMedia(DESKTOP_MEDIA_QUERY).matches
    isTouchLike.value = window.matchMedia(TOUCH_LIKE_MEDIA_QUERY).matches
  }

  onMounted(() => {
    if (typeof window === 'undefined') return
    const queries = [PHONE_MEDIA_QUERY, TABLET_MEDIA_QUERY, DESKTOP_MEDIA_QUERY, TOUCH_LIKE_MEDIA_QUERY]
    for (const query of queries) {
      const media = window.matchMedia(query)
      media.addEventListener('change', update)
      mediaQueries.push(media)
    }
    update()
  })

  onBeforeUnmount(() => {
    for (const media of mediaQueries) media.removeEventListener('change', update)
    mediaQueries.length = 0
  })

  return {
    isPhone,
    isTablet,
    isDesktop,
    isTouchLike,
  }
}
