#!/usr/bin/env node
/** Browser smoke coverage for the three development-stack login surfaces. */

import { createRequire } from 'node:module'

const require = createRequire('/smoke/package.json')
const { chromium } = require('playwright')

const smokeHost = process.env.SMOKE_HOST || 'host.docker.internal'
const tenantPort = process.env.HFL_TENANT_PORT || '11443'
const adminPort = process.env.HFL_ADMIN_PORT || '11444'
const sourceLensPort = process.env.SOURCELENS_CONSOLE_PORT || '11445'
const hflEmail = process.env.SEED_ADMIN_EMAIL || 'admin@hyperfilelens.com'
const hflPassword = process.env.SEED_ADMIN_PASSWORD || 'Admin@123'
const sourceLensUser = process.env.SOURCELENS_USER || 'admin'
const sourceLensPassword = process.env.SOURCELENS_PASSWORD || 'adminpassword'
const requireHmr = process.env.SMOKE_REQUIRE_HMR !== '0'

function fail(message) {
  throw new Error(message)
}

async function waitForHflLogin(page, baseUrl, expectedPathPrefix) {
  const unauthorized = []
  const webSockets = []
  page.on('response', response => {
    if (response.status() === 401) unauthorized.push(response.url())
  })
  page.on('websocket', socket => webSockets.push(socket.url()))

  await page.goto(`${baseUrl}/`, { waitUntil: 'networkidle' })
  await page.waitForURL(url => url.pathname.startsWith('/login'), { timeout: 30_000 })
  if (unauthorized.length) {
    fail(`pre-auth 401 response(s) at ${baseUrl}: ${unauthorized.join(', ')}`)
  }

  await page.locator('input[autocomplete="email"]').fill(hflEmail)
  await page.locator('input[autocomplete="current-password"]').fill(hflPassword)
  const captchaImage = page.locator('.auth-captcha-field__image')
  for (let attempt = 0; attempt < 2; attempt += 1) {
    try {
      await captchaImage.waitFor({ state: 'visible', timeout: attempt === 0 ? 15_000 : 30_000 })
      break
    } catch {
      if (attempt === 0) {
        const captchaRefresh = page.locator('.auth-captcha-field__image-button')
        if (await captchaRefresh.isVisible()) {
          await captchaRefresh.click()
          continue
        }
      }
      const captchaField = page.locator('.auth-captcha-field')
      const details = await captchaField.innerText().catch(() => '')
      fail(`image captcha did not become ready at ${baseUrl}: ${JSON.stringify(details)}`)
    }
  }
  const source = await captchaImage.getAttribute('src')
  if (!source?.startsWith('data:image/svg+xml;base64,')) {
    fail(`unexpected captcha image format at ${baseUrl}`)
  }
  const svg = Buffer.from(source.split(',', 2)[1], 'base64').toString('utf8')
  const captcha = [...svg.matchAll(/<text[^>]*>([^<])<\/text>/g)]
    .map(match => match[1])
    .join('')
  if (captcha.length !== 4) {
    fail(`unable to read the development SVG captcha at ${baseUrl}`)
  }
  await page.locator('.auth-captcha-field__input input').fill(captcha)
  await page.locator('button.submit-btn').click()
  await page.waitForURL(url => !url.pathname.startsWith('/login'), { timeout: 60_000 })
  if (!page.url().includes(expectedPathPrefix)) {
    fail(`unexpected post-login URL at ${baseUrl}: ${page.url()}`)
  }
  await page.waitForTimeout(1_000)
  if (requireHmr && !webSockets.some(url => url.includes('/__vite_hmr'))) {
    fail(`dedicated Vite HMR WebSocket was not observed at ${baseUrl}`)
  }
}

async function waitForPlatformOps(page, baseUrl) {
  const unauthorized = []
  page.on('response', response => {
    if (response.status() === 401) unauthorized.push(response.url())
  })

  await page.goto(`${baseUrl}/`, { waitUntil: 'domcontentloaded' })
  try {
    await page.waitForURL(url => url.pathname.startsWith('/platform-ops'), { timeout: 60_000 })
    await page.locator('.platform-ops-shell').waitFor({ state: 'visible', timeout: 60_000 })
  } catch {
    const body = (await page.locator('body').innerText().catch(() => '')).slice(0, 1_500)
    const cookies = await page.context().cookies().then(items => items.map(item => item.name))
    fail(
      `Platform Operations did not become ready at ${page.url()}; `
      + `cookies=${JSON.stringify(cookies)} body=${JSON.stringify(body)}`,
    )
  }
  if (unauthorized.length) {
    fail(`authenticated Platform Operations returned 401 response(s): ${unauthorized.join(', ')}`)
  }
}

async function waitForSourceLensLogin(page, baseUrl) {
  await page.goto(`${baseUrl}/login`, { waitUntil: 'networkidle' })
  const username = page.locator(
    'input[name="username"], input[autocomplete="username"], input[type="text"]',
  ).first()
  if (!(await username.isVisible())) {
    const switchButton = page.locator('button.block.w-full.text-center')
    await switchButton.click()
  }
  try {
    await username.waitFor({ state: 'visible', timeout: 10_000 })
  } catch {
    const buttons = await page.locator('button').allTextContents()
    const body = (await page.locator('body').innerText()).slice(0, 1_500)
    fail(
      `SourceLens password form did not appear at ${page.url()}; `
      + `buttons=${JSON.stringify(buttons)} body=${JSON.stringify(body)}`,
    )
  }
  await username.fill(sourceLensUser)
  await page.locator(
    'input[name="password"], input[autocomplete="current-password"], input[type="password"]',
  ).first().fill(sourceLensPassword)
  await page.locator('form button[type="submit"]').click()
  await page.waitForURL(url => !url.pathname.startsWith('/login'), { timeout: 60_000 })
}

async function run() {
  const browser = await chromium.launch({ headless: true })
  try {
    const hfl = await browser.newContext({ ignoreHTTPSErrors: true })
    await waitForHflLogin(
      await hfl.newPage(),
      `https://${smokeHost}:${tenantPort}`,
      '/',
    )
    await waitForPlatformOps(
      await hfl.newPage(),
      `https://${smokeHost}:${adminPort}`,
    )
    await hfl.close()

    const sourceLens = await browser.newContext({ ignoreHTTPSErrors: true })
    await waitForSourceLensLogin(
      await sourceLens.newPage(),
      `https://${smokeHost}:${sourceLensPort}`,
    )
    await sourceLens.close()
  } finally {
    await browser.close()
  }
  process.stdout.write(
    `browser smoke: tenant, Platform Ops, SourceLens${requireHmr ? ', and HMR' : ''} passed\n`,
  )
}

await run()
