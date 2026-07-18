import { ref } from 'vue'

export const isRouteTransitionPending = ref(false)

let transitionVersion = 0

export function beginRouteTransition() {
  transitionVersion += 1
  isRouteTransitionPending.value = true
}

export function finishRouteTransition() {
  const version = transitionVersion
  window.requestAnimationFrame(() => {
    if (version === transitionVersion) {
      isRouteTransitionPending.value = false
    }
  })
}
