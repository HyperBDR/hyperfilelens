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
  animation: auth-brand-enter 700ms cubic-bezier(0.16, 1, 0.3, 1) 220ms forwards;
}

.auth-brand-panel::after {
  content: '';
  position: absolute;
  left: -36px;
  top: -24px;
  width: 52px;
  height: calc(100% + 48px);
  background: linear-gradient(90deg, transparent, rgba(196, 181, 253, 0.18), transparent);
  filter: blur(5px);
  opacity: 0;
  transform: skewX(-12deg);
  animation: auth-brand-scan 920ms ease-out 360ms forwards;
  pointer-events: none;
}

.auth-logo-mark {
  position: relative;
  width: 72px;
  height: 72px;
  flex: 0 0 72px;
  border: 2px solid #8b5cf6;
  border-radius: 10px;
  background: #12111a;
  box-shadow: 0 0 34px rgba(139, 92, 246, 0.5);
  filter: drop-shadow(0 0 22px rgba(139, 92, 246, 0.52));
  transform: rotate(45deg);
}

.auth-logo-mark::before {
  content: '';
  position: absolute;
  inset: 16px;
  border-radius: 2px;
  background: #a78bfa;
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
  line-height: 1;
  text-shadow: 0 8px 28px rgba(0, 0, 0, 0.34);
}

.auth-logo-text > span {
  color: #ffcc4d;
  background: linear-gradient(110deg, #ffe6a3 0%, #ffcc4d 48%, #f6a72b 100%);
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
  padding: 5px 12px;
  border: 1px solid rgba(139, 92, 246, 0.42);
  border-radius: 999px;
  color: rgba(220, 211, 255, 0.92);
  background: rgba(83, 24, 130, 0.24);
  box-shadow:
    inset 0 0 14px rgba(109, 94, 246, 0.08),
    0 0 18px rgba(109, 94, 246, 0.08);
  font-size: 11px;
  font-weight: 650;
  letter-spacing: 0.055em;
  line-height: 1.4;
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
