<script setup lang="ts">
defineProps<{
  description: string
  slogan: string
}>()
</script>

<template>
  <div class="auth-brand-panel">
    <span
      class="auth-logo-mark"
      aria-hidden="true"
    >
      <span class="auth-logo-mark__beam auth-logo-mark__beam--a" />
      <span class="auth-logo-mark__beam auth-logo-mark__beam--b" />
      <span class="auth-logo-mark__core" />
    </span>

    <div class="auth-brand-copy">
      <span class="auth-logo-text"><span>Hyper</span><strong>FileLens</strong></span>
      <p class="auth-brand-description">
        {{ description }}
      </p>
      <p class="auth-brand-slogan">
        {{ slogan }}
      </p>
    </div>
  </div>
</template>

<style scoped>
.auth-brand-panel {
  position: relative;
  display: flex;
  align-items: center;
  gap: 22px;
  margin-bottom: 32px;
  opacity: 0;
  transform: translateY(10px);
  animation: auth-brand-enter 420ms cubic-bezier(0.16, 1, 0.3, 1) 60ms forwards;
}

.auth-brand-panel::after {
  content: '';
  position: absolute;
  left: -36px;
  top: -24px;
  width: 52px;
  height: calc(100% + 48px);
  background: linear-gradient(
    90deg,
    transparent,
    color-mix(in srgb, var(--color-brand-violet-soft) 18%, transparent),
    transparent
  );
  filter: blur(5px);
  opacity: 0;
  transform: skewX(-12deg);
  animation: auth-brand-scan 480ms ease-out 100ms forwards;
  pointer-events: none;
}

.auth-logo-mark {
  position: relative;
  width: 72px;
  height: 72px;
  flex: 0 0 72px;
  border: 2px solid var(--color-brand-violet-soft);
  border-radius: 10px;
  background: var(--color-header-bg);
  box-shadow: var(--shadow-brand-glow);
  transform: rotate(45deg);
}

.auth-logo-mark::before {
  content: '';
  position: absolute;
  inset: 16px;
  border-radius: 2px;
  background: var(--color-primary);
}

.auth-logo-mark__beam,
.auth-logo-mark__core {
  display: none;
}

.auth-brand-copy {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 7px;
}

.auth-logo-text {
  display: inline-flex;
  align-items: baseline;
  gap: 0;
  color: #fff;
  font-size: 48px;
  font-weight: 850;
  letter-spacing: -1.6px;
}

.auth-logo-text > span {
  color: var(--color-brand-gold);
  background: linear-gradient(
    110deg,
    color-mix(in srgb, var(--color-brand-gold) 55%, white) 0%,
    var(--color-brand-gold) 48%,
    color-mix(in srgb, var(--color-brand-gold) 82%, black) 100%
  );
  -webkit-background-clip: text;
  background-clip: text;
  font-weight: 850;
  -webkit-text-fill-color: transparent;
}

.auth-logo-text strong {
  color: #f8fafc;
  font-weight: 850;
}

.auth-brand-description {
  margin: 0;
  color: rgba(248, 250, 252, 0.88);
  font-size: 16px;
  font-weight: 500;
  letter-spacing: 0.025em;
  line-height: 1.45;
}

.auth-brand-slogan {
  margin: 8px 0 0;
  color: color-mix(in srgb, var(--color-brand-violet-soft) 92%, white);
  font-size: 13px;
  font-weight: 650;
  letter-spacing: 0.04em;
  line-height: 1.45;
  white-space: nowrap;
}

@keyframes auth-brand-enter {
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes auth-brand-scan {
  0% {
    opacity: 0;
    transform: translateX(0) skewX(-12deg);
  }

  28% {
    opacity: 1;
  }

  100% {
    opacity: 0;
    transform: translateX(520px) skewX(-12deg);
  }
}

@media (max-width: 1279.98px) {
  .auth-brand-panel {
    gap: 12px;
    margin: 0;
  }

  .auth-brand-description,
  .auth-brand-slogan {
    display: none;
  }

  .auth-logo-mark {
    width: 38px;
    height: 38px;
    flex-basis: 38px;
  }

  .auth-logo-mark::before {
    inset: 9px;
  }

  .auth-logo-text {
    font-size: 26px;
    letter-spacing: -0.8px;
  }
}

@media (max-width: 479.98px) {
  .auth-brand-description {
    display: block;
    color: rgba(248, 250, 252, 0.62);
    font-size: 12px;
    line-height: 1.35;
  }
}

@media (prefers-reduced-motion: reduce) {
  .auth-brand-panel {
    opacity: 1;
    transform: none;
    animation: none;
  }

  .auth-brand-panel::after {
    display: none;
  }
}
</style>
