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

const githubUrl = 'https://github.com/HyperBDR/hyperfilelens'
</script>

<template>
  <div class="hfl-site">
    <svg class="icon-sprite" aria-hidden="true">
      <symbol id="icon-arrow" viewBox="0 0 24 24">
        <path d="M5 12h14M13 6l6 6-6 6" />
      </symbol>
      <symbol id="icon-github" viewBox="0 0 24 24">
        <path d="M12 2a10 10 0 0 0-3.16 19.49c.5.09.68-.22.68-.48v-1.86c-2.78.6-3.37-1.18-3.37-1.18-.45-1.16-1.11-1.47-1.11-1.47-.91-.62.07-.61.07-.61 1 .07 1.53 1.03 1.53 1.03.9 1.53 2.35 1.09 2.92.83.09-.65.35-1.09.64-1.34-2.22-.25-4.55-1.11-4.55-4.94 0-1.09.39-1.98 1.03-2.68-.1-.25-.45-1.27.1-2.64 0 0 .84-.27 2.75 1.02A9.6 9.6 0 0 1 12 6.84a9.6 9.6 0 0 1 2.5.34c1.92-1.3 2.76-1.02 2.76-1.02.55 1.37.2 2.39.1 2.64.64.7 1.03 1.59 1.03 2.68 0 3.84-2.34 4.68-4.57 4.93.36.31.68.92.68 1.86v2.75c0 .27.18.58.69.48A10 10 0 0 0 12 2Z" fill="currentColor" stroke="none" />
      </symbol>
      <symbol id="icon-shield" viewBox="0 0 24 24">
        <path d="M12 3 5 6v5c0 4.6 2.8 8 7 10 4.2-2 7-5.4 7-10V6l-7-3Z" /><path d="m9 12 2 2 4-4" />
      </symbol>
      <symbol id="icon-network" viewBox="0 0 24 24">
        <rect x="9" y="3" width="6" height="6" rx="2" /><rect x="3" y="15" width="6" height="6" rx="2" /><rect x="15" y="15" width="6" height="6" rx="2" /><path d="M12 9v3M6 15v-3h12v3" />
      </symbol>
      <symbol id="icon-search" viewBox="0 0 24 24">
        <circle cx="11" cy="11" r="7" /><path d="m16 16 5 5" />
      </symbol>
      <symbol id="icon-restore" viewBox="0 0 24 24">
        <path d="M4 8v5h5" /><path d="M5.8 17.2A8 8 0 1 0 4.2 9" /><path d="M12 7v5l3 2" />
      </symbol>
      <symbol id="icon-server" viewBox="0 0 24 24">
        <rect x="3" y="4" width="18" height="6" rx="2" /><rect x="3" y="14" width="18" height="6" rx="2" /><path d="M7 7h.01M7 17h.01M11 7h6M11 17h6" />
      </symbol>
      <symbol id="icon-code" viewBox="0 0 24 24">
        <path d="m8 9-4 3 4 3M16 9l4 3-4 3M14 5l-4 14" />
      </symbol>
      <symbol id="icon-check" viewBox="0 0 24 24">
        <path d="m5 12 4 4L19 6" />
      </symbol>
      <symbol id="icon-building" viewBox="0 0 24 24">
        <path d="M4 21V5l8-3 8 3v16M8 8h2M14 8h2M8 12h2M14 12h2M8 16h2M14 16h2M2 21h20" />
      </symbol>
      <symbol id="icon-terminal" viewBox="0 0 24 24">
        <rect x="2" y="4" width="20" height="16" rx="2" /><path d="m6 9 3 3-3 3M12 15h5" />
      </symbol>
    </svg>

    <header class="site-header-wrap">
      <div class="site-header">
        <a class="brand" href="/en/" aria-label="HyperFileLens home">
          <img src="/logo-mark.svg" alt="" width="34" height="34" />
          <span>HyperFileLens</span>
        </a>
        <nav aria-label="Main navigation">
          <a href="#platform">Platform</a>
          <a href="#how-it-works">How it works</a>
          <a href="#use-cases">Use cases</a>
          <a href="#deploy">Deploy</a>
        </nav>
        <div class="header-actions">
          <a class="github-link" :href="githubUrl" aria-label="HyperFileLens on GitHub">
            <svg aria-hidden="true"><use href="#icon-github" /></svg>
            <span>GitHub</span>
          </a>
          <a class="header-cta" :href="loginUrl">Open app</a>
        </div>
      </div>
    </header>

    <main>
      <section class="hero" aria-labelledby="hero-title">
        <div class="hero-backdrop" aria-hidden="true"></div>
        <div class="hero-copy">
          <a class="open-source-pill" :href="githubUrl">
            <span class="pill-status"></span>
            Open source · Public beta
            <svg aria-hidden="true"><use href="#icon-arrow" /></svg>
          </a>
          <h1 id="hero-title">Your files, protected.<br /><span>Your knowledge, discoverable.</span></h1>
          <p class="hero-lead">
            HyperFileLens gives infrastructure teams one control plane to protect distributed file data,
            recover it with confidence, and turn trusted snapshots into useful AI knowledge.
          </p>
          <div class="hero-actions">
            <a class="button button-primary" :href="loginUrl">
              Open HyperFileLens
              <svg aria-hidden="true"><use href="#icon-arrow" /></svg>
            </a>
            <a class="button button-secondary" :href="githubUrl">
              <svg aria-hidden="true"><use href="#icon-github" /></svg>
              Explore the source
            </a>
          </div>
          <div class="hero-proof" aria-label="Key product qualities">
            <span><svg aria-hidden="true"><use href="#icon-check" /></svg>Self-hostable</span>
            <span><svg aria-hidden="true"><use href="#icon-check" /></svg>Offline-ready</span>
            <span><svg aria-hidden="true"><use href="#icon-check" /></svg>No source data migration</span>
          </div>
        </div>

        <div class="product-stage" aria-label="HyperFileLens control plane preview">
          <div class="product-window">
            <div class="window-bar">
              <div class="window-dots" aria-hidden="true"><i></i><i></i><i></i></div>
              <div class="window-title"><img src="/logo-mark.svg" alt="" />HyperFileLens</div>
              <div class="window-user" aria-hidden="true">OP</div>
            </div>
            <div class="product-shell">
              <aside aria-hidden="true">
                <span class="nav-mark active"><i></i>Overview</span>
                <span class="nav-mark"><i></i>Protection</span>
                <span class="nav-mark"><i></i>Recovery</span>
                <span class="nav-mark"><i></i>File Insight</span>
                <span class="nav-mark"><i></i>Data Gateways</span>
              </aside>
              <div class="dashboard">
                <div class="dashboard-heading"><div><small>Overview</small><strong>Good morning, Operator</strong></div><button tabindex="-1">New protection policy</button></div>
                <div class="metric-grid">
                  <div><span>Protected sources</span><strong>24</strong><small><i class="good"></i> All policies healthy</small></div>
                  <div><span>Latest snapshots</span><strong>156</strong><small><i class="good"></i> 12 completed today</small></div>
                  <div><span>Data gateways</span><strong>6</strong><small><i class="good"></i> All nodes online</small></div>
                </div>
                <div class="dashboard-grid">
                  <div class="activity-card">
                    <div class="card-heading"><strong>Protection activity</strong><span>Last 7 days</span></div>
                    <div class="bar-chart" aria-hidden="true">
                      <i style="--bar: 41%"></i><i style="--bar: 58%"></i><i style="--bar: 48%"></i><i style="--bar: 72%"></i><i style="--bar: 62%"></i><i style="--bar: 88%"></i><i style="--bar: 77%"></i>
                    </div>
                    <div class="chart-labels"><span>Mon</span><span>Tue</span><span>Wed</span><span>Thu</span><span>Fri</span><span>Sat</span><span>Sun</span></div>
                  </div>
                  <div class="source-card">
                    <div class="card-heading"><strong>Recent sources</strong><span>View all</span></div>
                    <div class="source-item"><span class="source-symbol blue"><svg><use href="#icon-server" /></svg></span><div><strong>Finance Archive</strong><small>2 min ago</small></div><b>Healthy</b></div>
                    <div class="source-item"><span class="source-symbol mint"><svg><use href="#icon-building" /></svg></span><div><strong>Product NAS</strong><small>18 min ago</small></div><b>Healthy</b></div>
                    <div class="source-item"><span class="source-symbol violet"><svg><use href="#icon-server" /></svg></span><div><strong>Research Files</strong><small>1 hr ago</small></div><b>Healthy</b></div>
                  </div>
                </div>
              </div>
            </div>
          </div>
          <div class="floating-status status-protected"><span><svg><use href="#icon-shield" /></svg></span><div><strong>Protection completed</strong><small>Finance Archive · just now</small></div></div>
          <div class="floating-status status-search"><span><svg><use href="#icon-search" /></svg></span><div><strong>Knowledge is ready</strong><small>156 snapshots indexed</small></div></div>
        </div>
      </section>

      <section class="trust-strip" aria-label="HyperFileLens capabilities">
        <p>Built for the realities of distributed file data</p>
        <div>
          <span>Central control plane</span><i></i><span>Distributed gateways</span><i></i><span>Kopia-powered protection</span><i></i><span>Optional AI intelligence</span>
        </div>
      </section>

      <section id="platform" class="section-block platform" aria-labelledby="platform-title">
        <div class="section-heading centered">
          <p class="section-kicker">One platform. The complete file lifecycle.</p>
          <h2 id="platform-title">Protection is only the beginning.</h2>
          <p>Keep operational control from first connection through recovery and knowledge discovery—without stitching together separate consoles.</p>
        </div>
        <div class="bento-grid">
          <article class="bento-card bento-protection">
            <div class="card-icon"><svg aria-hidden="true"><use href="#icon-shield" /></svg></div>
            <p class="card-label">Data protection</p>
            <h3>Policies that stay visible.</h3>
            <p>Coordinate sources, repositories, schedules, retention, snapshots, and recovery tasks from a single operational view.</p>
            <div class="policy-preview" aria-hidden="true">
              <div><span><i class="good"></i>Critical file policy</span><b>Healthy</b></div>
              <div class="policy-meter"><i></i></div>
              <small>Last snapshot 8 minutes ago · 2.8 TB protected</small>
            </div>
          </article>
          <article class="bento-card bento-gateway">
            <div class="card-icon mint"><svg aria-hidden="true"><use href="#icon-network" /></svg></div>
            <p class="card-label">Data Gateway</p>
            <h3>Reach data where it lives.</h3>
            <p>Connect private and remote environments through distributed gateways while keeping the control plane centralized.</p>
            <div class="gateway-map" aria-hidden="true">
              <span class="map-node node-core"><img src="/logo-mark.svg" alt="" /></span>
              <span class="map-node node-a"><svg><use href="#icon-server" /></svg></span>
              <span class="map-node node-b"><svg><use href="#icon-building" /></svg></span>
              <span class="map-node node-c"><svg><use href="#icon-server" /></svg></span>
              <i class="map-line line-a"></i><i class="map-line line-b"></i><i class="map-line line-c"></i>
            </div>
          </article>
          <article class="bento-card bento-insight">
            <div class="card-icon violet"><svg aria-hidden="true"><use href="#icon-search" /></svg></div>
            <p class="card-label">File intelligence</p>
            <h3>Ask trusted data better questions.</h3>
            <p>Use selected, protected snapshots as governed knowledge sources for discovery and AI-assisted workflows.</p>
            <div class="search-preview" aria-hidden="true">
              <svg><use href="#icon-search" /></svg><span>Find retention requirements in legal archives</span><kbd>↵</kbd>
            </div>
          </article>
          <article class="bento-card bento-recovery">
            <div class="card-icon amber"><svg aria-hidden="true"><use href="#icon-restore" /></svg></div>
            <p class="card-label">Recovery & audit</p>
            <h3>Recover with evidence.</h3>
            <p>Navigate snapshots, launch restore work, and preserve a traceable history of platform actions and outcomes.</p>
            <ul class="recovery-list">
              <li><svg><use href="#icon-check" /></svg>Snapshot-level recovery</li>
              <li><svg><use href="#icon-check" /></svg>Task and audit history</li>
              <li><svg><use href="#icon-check" /></svg>Operational alerts</li>
            </ul>
          </article>
        </div>
      </section>

      <section id="how-it-works" class="section-block flow-section" aria-labelledby="flow-title">
        <div class="section-heading flow-copy">
          <p class="section-kicker">Built around your infrastructure</p>
          <h2 id="flow-title">A control plane—not another data silo.</h2>
          <p>Deploy a lightweight Data Gateway close to each environment. HyperFileLens coordinates protection and intelligence centrally while your files remain where your teams already manage them.</p>
          <a class="text-link" :href="githubUrl">See the architecture on GitHub <svg aria-hidden="true"><use href="#icon-arrow" /></svg></a>
        </div>
        <div class="architecture" aria-label="HyperFileLens architecture flow">
          <div class="architecture-column source-column">
            <small>Your environments</small>
            <div><svg><use href="#icon-server" /></svg><span><strong>File servers</strong><em>Private networks</em></span></div>
            <div><svg><use href="#icon-building" /></svg><span><strong>NAS & archives</strong><em>Remote sites</em></span></div>
            <div><svg><use href="#icon-network" /></svg><span><strong>Object storage</strong><em>S3-compatible</em></span></div>
          </div>
          <div class="architecture-arrow" aria-hidden="true"><i></i><span>Secure orchestration</span></div>
          <div class="architecture-column control-column">
            <small>HyperFileLens</small>
            <div class="control-core"><img src="/logo-mark.svg" alt="" /><span><strong>Unified control plane</strong><em>Policies · tasks · audit</em></span></div>
            <div class="control-output"><span><svg><use href="#icon-shield" /></svg>Protected snapshots</span><span><svg><use href="#icon-search" /></svg>File intelligence</span></div>
          </div>
        </div>
      </section>

      <section id="use-cases" class="section-block use-cases" aria-labelledby="use-cases-title">
        <div class="section-heading centered">
          <p class="section-kicker">Made for teams responsible for data</p>
          <h2 id="use-cases-title">One foundation. Different jobs to be done.</h2>
        </div>
        <div class="use-case-grid">
          <article>
            <span class="use-case-number">01</span>
            <h3>Infrastructure & platform teams</h3>
            <p>Standardize protection across sites without losing visibility into nodes, policies, tasks, and capacity.</p>
            <ul><li>Distributed source management</li><li>Central health and task history</li><li>Repeatable protection policies</li></ul>
          </article>
          <article>
            <span class="use-case-number">02</span>
            <h3>Data owners & operations</h3>
            <p>Know that important files are recoverable and find the right snapshot when business work depends on it.</p>
            <ul><li>Clear protection status</li><li>Browsable snapshot history</li><li>Controlled restore workflows</li></ul>
          </article>
          <article>
            <span class="use-case-number">03</span>
            <h3>Knowledge & AI teams</h3>
            <p>Build searchable, scoped knowledge from protected content rather than another uncontrolled data copy.</p>
            <ul><li>Snapshot-backed knowledge sources</li><li>Configurable model providers</li><li>AI-assisted file discovery</li></ul>
          </article>
        </div>
      </section>

      <section class="open-source-section" aria-labelledby="open-source-title">
        <div class="open-source-grid">
          <div class="open-source-copy">
            <p class="section-kicker dark-kicker">Open source by design</p>
            <h2 id="open-source-title">Inspect it. Run it. Improve it.</h2>
            <p>HyperFileLens is built in public for teams that need transparency and deployment control. Review the architecture, follow development, or contribute directly on GitHub.</p>
            <div class="open-source-actions">
              <a class="button button-light" :href="githubUrl"><svg aria-hidden="true"><use href="#icon-github" /></svg>View on GitHub</a>
              <a class="source-link" :href="`${githubUrl}/releases`">Browse releases <svg aria-hidden="true"><use href="#icon-arrow" /></svg></a>
            </div>
            <p class="beta-note">HyperFileLens is currently in public beta.</p>
          </div>
          <div class="terminal-card" aria-label="Example HyperFileLens deployment command">
            <div class="terminal-bar"><span><i></i><i></i><i></i></span><b>deploy · bash</b></div>
            <pre><code><span class="terminal-comment"># Complete offline release bundle</span>
<span class="terminal-prompt">$</span> tar -xzf hyperfilelens-release.tar.gz
<span class="terminal-prompt">$</span> cd hyperfilelens
<span class="terminal-prompt">$</span> sudo ./install.sh install

<span class="terminal-success">✓</span> Environment validated
<span class="terminal-success">✓</span> Images loaded locally
<span class="terminal-success">✓</span> HyperFileLens is ready</code></pre>
          </div>
        </div>
      </section>

      <section id="deploy" class="section-block deployment" aria-labelledby="deployment-title">
        <div class="section-heading deployment-heading">
          <div><p class="section-kicker">Deploy on your terms</p><h2 id="deployment-title">From managed access to offline infrastructure.</h2></div>
          <p>Choose the operating model that fits your environment today without giving up a path to more control later.</p>
        </div>
        <div class="deployment-grid">
          <article>
            <div class="deployment-icon"><svg><use href="#icon-network" /></svg></div>
            <span>Fastest start</span>
            <h3>Hosted service</h3>
            <p>Use the managed HyperFileLens control plane and connect your environments through Data Gateways.</p>
            <a :href="loginUrl">Open the app <svg><use href="#icon-arrow" /></svg></a>
          </article>
          <article class="featured-deployment">
            <div class="deployment-icon"><svg><use href="#icon-server" /></svg></div>
            <span>Full control</span>
            <h3>Self-hosted</h3>
            <p>Run the complete platform inside your own Ubuntu amd64 environment using the packaged installer.</p>
            <a :href="`${githubUrl}/releases`">View releases <svg><use href="#icon-arrow" /></svg></a>
          </article>
          <article>
            <div class="deployment-icon"><svg><use href="#icon-terminal" /></svg></div>
            <span>Restricted networks</span>
            <h3>Offline-ready</h3>
            <p>Install from a complete image-only release bundle when the target environment cannot reach the internet.</p>
            <a :href="`${githubUrl}#requirements`">Read requirements <svg><use href="#icon-arrow" /></svg></a>
          </article>
        </div>
      </section>

      <section class="final-cta" aria-labelledby="cta-title">
        <div class="cta-glow" aria-hidden="true"></div>
        <div>
          <p class="section-kicker dark-kicker">Start with a clearer view of your data</p>
          <h2 id="cta-title">Protect the files you rely on.<br />Put their knowledge to work.</h2>
        </div>
        <div class="cta-actions">
          <a class="button button-light" :href="loginUrl">Open HyperFileLens <svg aria-hidden="true"><use href="#icon-arrow" /></svg></a>
          <a class="button button-dark-outline" :href="githubUrl"><svg aria-hidden="true"><use href="#icon-github" /></svg>Explore GitHub</a>
        </div>
      </section>
    </main>

    <footer>
      <div class="footer-brand">
        <a class="brand" href="/en/"><img src="/logo-mark.svg" alt="" width="32" height="32" /><span>HyperFileLens</span></a>
        <p>Open-source data protection and file intelligence.</p>
      </div>
      <div class="footer-links">
        <div><strong>Product</strong><a href="#platform">Platform</a><a href="#how-it-works">How it works</a><a href="#deploy">Deployment</a></div>
        <div><strong>Open source</strong><a :href="githubUrl">GitHub</a><a :href="`${githubUrl}/releases`">Releases</a><a :href="`${githubUrl}/issues`">Issues</a></div>
        <div><strong>Access</strong><a :href="loginUrl">Open app</a><a href="/en/">English</a></div>
      </div>
      <div class="footer-bottom"><span>© 2026 HyperFileLens contributors</span><span>Public beta · Built in the open</span></div>
    </footer>
  </div>
</template>
