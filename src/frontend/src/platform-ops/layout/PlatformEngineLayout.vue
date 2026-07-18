<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'
import ModulePage from '../../components/ModulePage.vue'
import { usePlatformOpsSideNav } from '../composables/usePlatformOpsSideNav'
import { setLensApiScope } from '../../lib/lensApi'

defineOptions({ name: 'PlatformEngineLayout' })

setLensApiScope('platform')

onMounted(() => {
  setLensApiScope('platform')
})

onUnmounted(() => {
  // Only reset when leaving Admin Engine; child route changes keep this layout mounted.
  setLensApiScope('tenant')
})

const sideNav = usePlatformOpsSideNav()
</script>

<template>
  <ModulePage :menus="sideNav" body-fill>
    <router-view />
  </ModulePage>
</template>
