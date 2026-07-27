<script setup lang="ts">
import DefaultTheme from 'vitepress/theme'
import { useData } from 'vitepress'
import HomeLanding from './HomeLanding.vue'

const { frontmatter } = useData()
</script>

<template>
  <HomeLanding v-if="frontmatter.layout === 'hfl-home'" />
  <DefaultTheme.Layout v-else />
</template>
