<script setup lang="ts">
import { computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
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
const route = useRoute()
const hidePageTitle = computed(() => /\/(?:add|edit)$/.test(route.path))
</script>

<template>
  <ModulePage :menus="sideNav" body-fill :hide-page-title="hidePageTitle">
    <router-view />
  </ModulePage>
</template>
