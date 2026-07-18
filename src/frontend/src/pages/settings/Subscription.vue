<script setup lang="ts">
import SubscriptionContent from './SubscriptionContent.vue'
import { useNodeSideNav } from '../../composables/useNodeSideNav'
import ModulePage from '../../components/ModulePage.vue'

const nodeMenus = useNodeSideNav()
</script>

<template>
  <ModulePage :menus="nodeMenus">
    <SubscriptionContent />
  </ModulePage>
</template>
