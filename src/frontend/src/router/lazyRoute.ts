import { defineAsyncComponent, defineComponent, h, type Component } from 'vue'
import { ChunkLoadError } from './ChunkLoadError'
import {
  clearChunkLoadFailureAttempt,
  isDynamicImportFailure,
  reloadOnceForChunkLoadFailure,
} from './chunkLoadRecovery'

type RouteLoader = () => Promise<{ default: Component }>

export function lazyRoute(loader: RouteLoader): Component {
  const AsyncPage = defineAsyncComponent({
    loader,
    suspensible: true,
    errorComponent: ChunkLoadError,
    onError(error, _retry, fail) {
      if (isDynamicImportFailure(error) && reloadOnceForChunkLoadFailure()) return
      fail()
    },
  })

  return defineComponent({
    name: 'LazyRouteView',
    setup() {
      return () => h(AsyncPage, {
        onVnodeMounted: () => clearChunkLoadFailureAttempt(),
      })
    },
  })
}
