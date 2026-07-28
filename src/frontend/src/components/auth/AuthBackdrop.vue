<template>
  <div
    class="auth-backdrop"
    aria-hidden="true"
  >
    <div class="auth-backdrop__image" />
    <div class="auth-backdrop__ambient" />

    <div class="auth-backdrop__optics">
      <span class="auth-backdrop__ring auth-backdrop__ring--outer" />
      <span class="auth-backdrop__ring auth-backdrop__ring--telemetry" />
      <span class="auth-backdrop__ring auth-backdrop__ring--middle" />
      <span class="auth-backdrop__ring auth-backdrop__ring--inner" />
      <span class="auth-backdrop__ring auth-backdrop__ring--core" />
      <span class="auth-backdrop__ticks" />
      <span class="auth-backdrop__arc auth-backdrop__arc--amber" />
      <span class="auth-backdrop__arc auth-backdrop__arc--violet" />
      <span class="auth-backdrop__node auth-backdrop__node--one" />
      <span class="auth-backdrop__node auth-backdrop__node--two" />
      <span class="auth-backdrop__node auth-backdrop__node--three" />
    </div>

    <div class="auth-backdrop__veil" />
  </div>
</template>

<style scoped>
.auth-backdrop {
  position: absolute;
  inset: 0;
  z-index: 0;
  overflow: hidden;
  pointer-events: none;
  background:
    radial-gradient(circle at 38% 48%, rgba(104, 78, 126, 0.14), transparent 26%),
    radial-gradient(circle at 14% 8%, rgba(74, 54, 112, 0.13), transparent 32%),
    linear-gradient(135deg, #0d0914 0%, #090811 48%, #06070d 100%);
}

.auth-backdrop__image,
.auth-backdrop__ambient,
.auth-backdrop__optics,
.auth-backdrop__veil {
  position: absolute;
}

.auth-backdrop__image {
  inset: -2%;
  background-image: url('/assets/bg.png');
  background-position: center;
  background-size: cover;
  filter: saturate(0.6) contrast(1.05) brightness(0.76);
  mix-blend-mode: screen;
  -webkit-mask-image: linear-gradient(
    180deg,
    transparent 0%,
    rgba(0, 0, 0, 0.38) 20%,
    #000 54%,
    rgba(0, 0, 0, 0.72) 100%
  );
  mask-image: linear-gradient(
    180deg,
    transparent 0%,
    rgba(0, 0, 0, 0.38) 20%,
    #000 54%,
    rgba(0, 0, 0, 0.72) 100%
  );
  transform: scale(1.01);
}

.auth-backdrop__ambient {
  left: clamp(220px, 36vw, 690px);
  top: 50%;
  width: min(70vw, 920px);
  aspect-ratio: 1;
  border-radius: 50%;
  background:
    radial-gradient(circle, color-mix(in srgb, var(--color-brand-gold) 9%, transparent), transparent 24%),
    radial-gradient(circle, color-mix(in srgb, var(--color-primary) 10%, transparent), transparent 58%);
  filter: blur(12px);
  transform: translate(-50%, -50%);
}

.auth-backdrop__optics {
  left: clamp(340px, 36vw, 690px);
  top: 50%;
  width: clamp(760px, 72vw, 1120px);
  aspect-ratio: 1;
  border-radius: 50%;
  opacity: 0;
  transform: translate(-50%, -50%);
  animation: auth-optics-enter 480ms cubic-bezier(0.16, 1, 0.3, 1) 60ms forwards;
}

.auth-backdrop__optics::before,
.auth-backdrop__optics::after {
  content: '';
  position: absolute;
  border-radius: 50%;
}

.auth-backdrop__optics::before {
  inset: 28%;
  background: radial-gradient(
    circle,
    color-mix(in srgb, var(--color-primary) 8%, transparent),
    color-mix(in srgb, var(--color-brand-gold) 3.5%, transparent) 38%,
    transparent 70%
  );
  filter: blur(18px);
}

.auth-backdrop__optics::after {
  inset: 11%;
  background: conic-gradient(
    from 2deg,
    transparent 0deg 26deg,
    color-mix(in srgb, var(--color-brand-violet-soft) 14%, transparent) 26deg 27deg,
    transparent 27deg 88deg,
    color-mix(in srgb, var(--color-brand-gold) 14%, transparent) 88deg 89deg,
    transparent 89deg 188deg,
    color-mix(in srgb, var(--color-brand-violet-soft) 12%, transparent) 188deg 189deg,
    transparent 189deg 360deg
  );
  -webkit-mask: radial-gradient(farthest-side, transparent calc(100% - 11px), #000 0);
  mask: radial-gradient(farthest-side, transparent calc(100% - 11px), #000 0);
}

.auth-backdrop__ring,
.auth-backdrop__ticks,
.auth-backdrop__arc,
.auth-backdrop__node {
  position: absolute;
  border-radius: 50%;
}

.auth-backdrop__ring {
  border: 1px solid color-mix(in srgb, var(--color-brand-violet-soft) 10%, transparent);
}

.auth-backdrop__ring--outer {
  inset: 0;
  border-color: color-mix(in srgb, var(--color-brand-violet-soft) 10.5%, transparent);
}

.auth-backdrop__ring--telemetry {
  inset: 7%;
  border-style: dashed;
  border-color: color-mix(in srgb, var(--color-brand-violet-soft) 11%, transparent);
}

.auth-backdrop__ring--middle {
  inset: 17%;
  border-color: color-mix(in srgb, var(--color-primary) 9%, transparent);
}

.auth-backdrop__ring--inner {
  inset: 29%;
  border-style: dashed;
  border-color: color-mix(in srgb, var(--color-brand-violet-soft) 11.5%, transparent);
}

.auth-backdrop__ring--core {
  inset: 39%;
  border-color: color-mix(in srgb, var(--color-brand-gold) 9.5%, transparent);
}

.auth-backdrop__ticks {
  inset: 3.5%;
  background: repeating-conic-gradient(
    from 0deg,
    color-mix(in srgb, var(--color-brand-violet-soft) 18%, transparent) 0deg 0.32deg,
    transparent 0.32deg 7.5deg
  );
  -webkit-mask: radial-gradient(farthest-side, transparent calc(100% - 12px), #000 0);
  mask: radial-gradient(farthest-side, transparent calc(100% - 12px), #000 0);
  opacity: 0.58;
}

.auth-backdrop__arc {
  background: conic-gradient(from 0deg, currentColor, transparent 36deg 360deg);
  -webkit-mask: radial-gradient(farthest-side, transparent calc(100% - 3px), #000 0);
  mask: radial-gradient(farthest-side, transparent calc(100% - 3px), #000 0);
}

.auth-backdrop__arc--amber {
  inset: 17%;
  color: color-mix(in srgb, var(--color-brand-gold) 22%, transparent);
  transform: rotate(76deg);
}

.auth-backdrop__arc--violet {
  inset: 29%;
  color: color-mix(in srgb, var(--color-brand-violet-soft) 20%, transparent);
  transform: rotate(218deg);
}

.auth-backdrop__node {
  width: 7px;
  height: 7px;
  background: var(--color-primary);
  box-shadow: var(--shadow-brand-glow);
}

.auth-backdrop__node--one {
  left: 55%;
  top: 20%;
  opacity: 0.48;
}

.auth-backdrop__node--two {
  left: 28%;
  top: 48%;
  width: 5px;
  height: 5px;
  background: #5ca6cf;
  opacity: 0.36;
}

.auth-backdrop__node--three {
  right: 13%;
  bottom: 25%;
  width: 4px;
  height: 4px;
  background: var(--color-brand-gold);
  opacity: 0.34;
}

.auth-backdrop__veil {
  inset: 0;
  background:
    linear-gradient(90deg, transparent 0%, rgba(5, 6, 12, 0.04) 46%, rgba(5, 6, 12, 0.48) 72%, rgba(4, 5, 9, 0.82) 100%),
    radial-gradient(circle at 76% 50%, transparent 12%, rgba(4, 5, 9, 0.12) 34%, rgba(4, 5, 9, 0.36) 100%);
}

@keyframes auth-optics-enter {
  from {
    opacity: 0;
    transform: translate(-50%, calc(-50% + 12px)) scale(0.985);
  }

  to {
    opacity: 1;
    transform: translate(-50%, -50%) scale(1);
  }
}

@media (max-width: 1279.98px) {
  .auth-backdrop__image {
    background-position: 62% center;
    filter: saturate(0.52) contrast(1.03) brightness(0.7);
    opacity: 0.11;
  }

  .auth-backdrop__ambient {
    left: 50%;
    top: 128px;
    width: min(120vw, 760px);
  }

  .auth-backdrop__optics {
    left: 50%;
    top: 118px;
    width: min(94vw, 820px);
    opacity: 0.72;
    animation: none;
  }

  .auth-backdrop__veil {
    background: linear-gradient(180deg, rgba(5, 6, 11, 0.26), rgba(5, 6, 11, 0.7));
  }
}

@media (max-width: 479.98px) {
  .auth-backdrop__image {
    opacity: 0.08;
  }

  .auth-backdrop__optics {
    top: 78px;
    width: 680px;
    opacity: 0.48;
  }

  .auth-backdrop__ambient {
    top: 78px;
    width: 620px;
    opacity: 0.72;
  }
}

@media (max-width: 767.98px), (update: slow) {
  .auth-backdrop__image {
    filter: none;
    mix-blend-mode: normal;
    -webkit-mask-image: none;
    mask-image: none;
    transform: none;
  }

  .auth-backdrop__ambient {
    display: none;
  }

  .auth-backdrop__optics::before {
    filter: none;
  }
}

@media (prefers-reduced-motion: reduce) {
  .auth-backdrop__optics {
    opacity: 1;
    animation: none;
  }
}
</style>
