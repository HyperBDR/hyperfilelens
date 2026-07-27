import { defineConfig } from 'vitepress'

export default defineConfig({
  lang: 'en-US',
  title: 'HyperFileLens',
  description: 'Protect, understand, and recover your files with confidence.',
  cleanUrls: true,
  head: [
    ['meta', { name: 'theme-color', content: '#07111f' }],
    ['meta', { name: 'viewport', content: 'width=device-width, initial-scale=1' }],
    ['meta', { property: 'og:type', content: 'website' }],
    ['meta', { property: 'og:title', content: 'HyperFileLens' }],
    ['meta', { property: 'og:description', content: 'Protect, understand, and recover your files with confidence.' }],
    ['script', { src: '/website-runtime-config.js' }],
  ],
  themeConfig: {
    logo: '/logo-mark.svg',
    siteTitle: 'HyperFileLens',
  },
})
