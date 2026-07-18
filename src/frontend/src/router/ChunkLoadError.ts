import { defineComponent, h } from 'vue'

export const ChunkLoadError = defineComponent({
  name: 'ChunkLoadError',
  setup() {
    return () => h('section', { class: 'chunk-load-error', role: 'alert' }, [
      h('h1', 'Page update detected'),
      h('p', 'This page resource is no longer available. Reload to continue with the latest version.'),
      h('button', {
        type: 'button',
        onClick: () => window.location.reload(),
      }, 'Reload page'),
    ])
  },
})
