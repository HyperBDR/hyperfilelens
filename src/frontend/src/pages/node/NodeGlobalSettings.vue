<script setup lang="ts">
import ModulePage from '../../components/ModulePage.vue'
import { useNodeSideNav } from '../../composables/useNodeSideNav'
import GlobalSettingsContent from '../settings/GlobalSettingsContent.vue'

const nodeMenus = useNodeSideNav()
</script>

<template>
  <ModulePage :menus="nodeMenus">
    <GlobalSettingsContent />
  </ModulePage>
</template>
