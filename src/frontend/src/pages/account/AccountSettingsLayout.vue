<script setup lang="ts">
import { RouterView } from 'vue-router'
import ModulePage from '../../components/ModulePage.vue'
import { useAccountCenterMenus } from '../../composables/useAccountCenterMenus'

const accountMenus = useAccountCenterMenus()
</script>

<template>
  <ModulePage :menus="accountMenus">
    <RouterView v-slot="{ Component }">
      <Transition name="account-route" mode="out-in">
        <component :is="Component" />
      </Transition>
    </RouterView>
  </ModulePage>
</template>

<style scoped>
.account-route-enter-active,
.account-route-leave-active {
  transition: opacity 0.2s ease;
}

.account-route-enter-from,
.account-route-leave-to {
  opacity: 0;
}
</style>
