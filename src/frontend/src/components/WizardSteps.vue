<script setup lang="ts">
import type { Component } from 'vue'

type WizardStepValue = string | number

export interface WizardStepItem {
  step: WizardStepValue
  label: string
  icon?: Component
}

const props = withDefaults(defineProps<{
  steps: WizardStepItem[]
  currentStep: WizardStepValue
  ariaLabel?: string
  clickable?: boolean
  as?: string
  isDone?: (step: WizardStepValue, index: number) => boolean
  isLocked?: (step: WizardStepValue, index: number) => boolean
}>(), {
  ariaLabel: undefined,
  clickable: true,
  as: 'nav',
  isDone: undefined,
  isLocked: undefined,
})

const emit = defineEmits<{
  'step-click': [step: WizardStepValue, index: number]
}>()

function stepKey(item: WizardStepItem, index: number) {
  return `${String(item.step)}-${index}`
}

function isStepActive(item: WizardStepItem) {
  return item.step === props.currentStep
}

function isStepDone(item: WizardStepItem, index: number) {
  return props.isDone?.(item.step, index) ?? false
}

function isStepLocked(item: WizardStepItem, index: number) {
  return props.isLocked?.(item.step, index) ?? false
}

function onStepClick(item: WizardStepItem, index: number) {
  if (!props.clickable) return
  emit('step-click', item.step, index)
}
</script>

<template>
  <component
    :is="as"
    class="wizard-steps"
    :aria-label="ariaLabel"
  >
    <template
      v-for="(item, index) in steps"
      :key="stepKey(item, index)"
    >
      <button
        v-if="clickable"
        type="button"
        class="wizard-steps__item"
        :class="{
          'wizard-steps__item--active': isStepActive(item),
          'wizard-steps__item--done': isStepDone(item, index),
          'wizard-steps__item--locked': isStepLocked(item, index),
        }"
        :aria-current="isStepActive(item) ? 'step' : undefined"
        @click="onStepClick(item, index)"
      >
        <span class="wizard-steps__num">
          <template v-if="isStepDone(item, index)">✓</template>
          <component
            v-else-if="item.icon"
            :is="item.icon"
            class="wizard-steps__icon"
            :size="14"
            stroke-width="2"
            aria-hidden="true"
          />
          <template v-else>{{ index + 1 }}</template>
        </span>
        <span class="wizard-steps__label">{{ item.label }}</span>
      </button>
      <div
        v-else
        class="wizard-steps__item"
        :class="{
          'wizard-steps__item--active': isStepActive(item),
          'wizard-steps__item--done': isStepDone(item, index),
          'wizard-steps__item--locked': isStepLocked(item, index),
        }"
        :aria-current="isStepActive(item) ? 'step' : undefined"
      >
        <span class="wizard-steps__num">
          <template v-if="isStepDone(item, index)">✓</template>
          <component
            v-else-if="item.icon"
            :is="item.icon"
            class="wizard-steps__icon"
            :size="14"
            stroke-width="2"
            aria-hidden="true"
          />
          <template v-else>{{ index + 1 }}</template>
        </span>
        <span class="wizard-steps__label">{{ item.label }}</span>
      </div>
      <div
        v-if="index < steps.length - 1"
        class="wizard-steps__connector"
        :class="{ 'wizard-steps__connector--on': isStepDone(item, index) }"
        aria-hidden="true"
      />
    </template>
  </component>
</template>

<style scoped>
.wizard-steps {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  width: 190px;
  max-width: none;
  min-height: 0;
  flex-shrink: 0;
  gap: 0;
  margin: 0;
  padding: 8px 0 0;
  overflow: visible;
  border: 0;
  border-radius: 0;
  background: transparent;
  box-shadow: none;
}

.wizard-steps__item {
  display: flex;
  align-items: center;
  min-width: 0;
  gap: 10px;
  padding: 0;
  border: 0;
  background: transparent;
  opacity: 0.5;
  color: inherit;
  cursor: default;
  transition: opacity 0.2s ease;
}

button.wizard-steps__item {
  cursor: pointer;
}

.wizard-steps__item--active,
.wizard-steps__item--done {
  opacity: 1;
}

.wizard-steps__item--locked {
  opacity: 0.45;
}

.wizard-steps__num {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  flex: 0 0 28px;
  border-radius: 50%;
  font-size: 12px;
  font-weight: 600;
  background: rgb(248 250 252);
  border: 1px solid rgba(203, 213, 225, 0.95);
  color: rgb(100 116 139);
  box-shadow: none;
  transition: all 0.2s ease;
}

.wizard-steps__item--active .wizard-steps__num,
.wizard-steps__item--done .wizard-steps__num {
  background: var(--color-primary);
  border-color: var(--color-primary);
  color: #fff;
  box-shadow: none;
}

.wizard-steps__icon {
  width: 14px;
  height: 14px;
  flex: 0 0 14px;
}

.wizard-steps__label {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 14px;
  font-weight: 500;
  line-height: normal;
  color: rgb(30 41 59);
}

.wizard-steps__connector {
  display: block;
  width: 1px;
  height: 28px;
  min-height: 28px;
  flex: 0 0 28px;
  max-width: none;
  margin: 5px 0 5px 14px;
  border-top: 0;
  background: rgba(203, 213, 225, 0.9);
  border-radius: 1px;
  transition: background 0.3s ease;
}

.wizard-steps__connector--on {
  border-top-color: transparent;
  background: var(--color-primary);
}

@media (max-width: 768px) {
  .wizard-steps {
    width: 100%;
  }

  .wizard-steps__connector {
    height: 20px;
    min-height: 20px;
    flex-basis: 20px;
  }
}
</style>
