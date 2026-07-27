<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

declare global {
  interface Window {
    __HFL_WEBSITE_CONFIG__?: { appUrl?: string }
  }
}

const appOrigin = ref('')

function validOrigin(value: string): string {
  try {
    const parsed = new URL(value)
    if (!['http:', 'https:'].includes(parsed.protocol) || parsed.username || parsed.password) return ''
    if (parsed.pathname !== '/' || parsed.search || parsed.hash) return ''
    return parsed.origin
  } catch {
    return ''
  }
}

function directAppOrigin(): string {
  const hostname = window.location.hostname || '127.0.0.1'
  const host = hostname.includes(':') ? `[${hostname}]` : hostname
  return `https://${host}:11443`
}

onMounted(() => {
  appOrigin.value = validOrigin(window.__HFL_WEBSITE_CONFIG__?.appUrl || '') || directAppOrigin()
})

const loginUrl = computed(() => `${appOrigin.value || '#'}${appOrigin.value ? '/login' : ''}`)
</script>

<template>
  <div class="hfl-site">
    <header class="site-header">
      <a class="brand" href="/en/" aria-label="HyperFileLens home">
        <img src="/logo-mark.svg" alt="" width="34" height="34" />
        <span>HyperFileLens</span>
      </a>
      <nav aria-label="Main navigation">
        <a href="#features">Features</a>
        <a href="#workflow">How it works</a>
        <a href="#deployment">Deployment</a>
        <a href="https://github.com/HyperBDR/hyperfilelens">GitHub</a>
      </nav>
      <a class="header-cta" :href="loginUrl">Sign in</a>
    </header>

    <main>
      <section class="hero" aria-labelledby="hero-title">
        <div class="hero-copy">
          <p class="eyebrow">Data protection meets file intelligence</p>
          <h1 id="hero-title">Protect, understand, and recover your files with confidence.</h1>
          <p class="hero-lead">
            HyperFileLens combines dependable data protection, distributed Data Gateways,
            and AI-powered file intelligence in one clear platform.
          </p>
          <div class="hero-actions">
            <a class="button button-primary" :href="loginUrl">Open HyperFileLens</a>
            <a class="button button-secondary" href="https://github.com/HyperBDR/hyperfilelens">View on GitHub</a>
          </div>
          <p class="hero-note">SaaS, self-hosted, and offline-ready.</p>
        </div>
        <div class="hero-visual" aria-label="HyperFileLens protection workflow overview">
          <div class="visual-glow"></div>
          <div class="visual-card visual-source">
            <span class="visual-label">FILE SOURCES</span>
            <strong>Files across every location</strong>
            <div class="source-lines"><i></i><i></i><i></i></div>
          </div>
          <div class="flow-line"></div>
          <div class="visual-card visual-lens">
            <span class="visual-label">HYPERFILELENS</span>
            <strong>Protected and understood</strong>
            <div class="status-row"><span>Protection</span><b>Healthy</b></div>
            <div class="status-row"><span>AI insight</span><b>Ready</b></div>
          </div>
        </div>
      </section>

      <section id="features" class="section-block" aria-labelledby="features-title">
        <p class="section-kicker">One platform, complete visibility</p>
        <h2 id="features-title">Everything you need to protect file data and put it to work.</h2>
        <div class="feature-grid">
          <article>
            <div class="feature-icon" aria-hidden="true">01</div>
            <h3>Data Protection</h3>
            <p>Policy-driven backups, retention, recovery, and clear operational status for critical files.</p>
          </article>
          <article>
            <div class="feature-icon" aria-hidden="true">02</div>
            <h3>Data Gateway</h3>
            <p>Bring remote and private file sources into one control plane without moving your infrastructure.</p>
          </article>
          <article>
            <div class="feature-icon" aria-hidden="true">03</div>
            <h3>AI File Intelligence</h3>
            <p>Turn protected content into searchable knowledge for faster discovery and better decisions.</p>
          </article>
          <article>
            <div class="feature-icon" aria-hidden="true">04</div>
            <h3>Recovery and Audit</h3>
            <p>Restore with confidence and keep a traceable record of tasks, policies, and platform activity.</p>
          </article>
        </div>
      </section>

      <section id="workflow" class="section-block workflow" aria-labelledby="workflow-title">
        <div>
          <p class="section-kicker">Simple by design</p>
          <h2 id="workflow-title">From file source to protected knowledge in four steps.</h2>
        </div>
        <ol>
          <li><span>01</span><div><h3>Deploy a Data Gateway</h3><p>Connect the environments where your files already live.</p></div></li>
          <li><span>02</span><div><h3>Add file sources</h3><p>Register directories and repositories through one console.</p></div></li>
          <li><span>03</span><div><h3>Apply protection policies</h3><p>Control backup, retention, and recovery behavior.</p></div></li>
          <li><span>04</span><div><h3>Search, analyze, and recover</h3><p>Use protected data with operational and AI-powered insight.</p></div></li>
        </ol>
      </section>

      <section id="deployment" class="section-block deployment" aria-labelledby="deployment-title">
        <p class="section-kicker">Built for real environments</p>
        <h2 id="deployment-title">Run it where your data and operating model require.</h2>
        <div class="deployment-grid">
          <div><strong>SaaS</strong><span>Start quickly with a managed control plane.</span></div>
          <div><strong>Self-hosted</strong><span>Operate HyperFileLens inside your environment.</span></div>
          <div><strong>Offline-ready</strong><span>Install from a complete release bundle without internet access.</span></div>
        </div>
      </section>

      <section class="final-cta" aria-labelledby="cta-title">
        <div>
          <p class="section-kicker">Start with clarity</p>
          <h2 id="cta-title">Ready to protect and understand your files?</h2>
        </div>
        <a class="button button-light" :href="loginUrl">Open HyperFileLens</a>
      </section>
    </main>

    <footer>
      <a class="brand" href="/en/"><img src="/logo-mark.svg" alt="" width="28" height="28" /><span>HyperFileLens</span></a>
      <p>Data protection and file intelligence, working together.</p>
      <div><a href="https://github.com/HyperBDR/hyperfilelens">GitHub</a><a href="/en/">English</a></div>
    </footer>
  </div>
</template>
