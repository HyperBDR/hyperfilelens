import { defineConfig } from 'vitepress'

export default defineConfig({
  lang: 'en-US',
  title: 'HyperFileLens',
  description: 'Open-source data protection and file intelligence for distributed infrastructure.',
  cleanUrls: true,
  head: [
    ['link', { rel: 'icon', type: 'image/svg+xml', href: '/logo-mark.svg' }],
    ['meta', { name: 'theme-color', content: '#07111f' }],
    ['meta', { name: 'viewport', content: 'width=device-width, initial-scale=1' }],
    ['meta', { property: 'og:type', content: 'website' }],
    ['meta', { property: 'og:title', content: 'HyperFileLens — Protect files. Discover knowledge.' }],
    ['meta', { property: 'og:description', content: 'Open-source data protection and file intelligence for distributed infrastructure.' }],
    ['meta', { name: 'twitter:card', content: 'summary' }],
    ['script', { src: '/website-runtime-config.js' }],
  ],
  themeConfig: {
    logo: '/logo-mark.svg',
    siteTitle: 'HyperFileLens',
  },
})
