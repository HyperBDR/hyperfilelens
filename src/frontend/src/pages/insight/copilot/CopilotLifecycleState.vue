<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { AlertCircle, Check, Circle, LoaderCircle, Sparkles } from 'lucide-vue-next'
import {
  conversionCountsLabel,
  conversionPhase,
  conversionProblemItems,
  conversionWarningsForDisplay,
} from '../../../lib/conversionSummary'
import type { LensSessionLink } from '../../../lib/lensApi'

const props = defineProps<{
  session: LensSessionLink
}>()

const emit = defineEmits<{
  retry: []
  delete: []
}>()

const { t } = useI18n()

const steps = [
  { label: 'Validating Selected Data', phases: ['queued'] },
  { label: 'Preparing Files and Folders', phases: ['restoring'] },
  { label: 'Extracting Document Content', phases: ['converting'] },
  { label: 'Indexing Selected Content', phases: ['creating_knowledge_source'] },
  { label: 'Getting AI Copilot Ready', phases: ['creating_assistant', 'granting_assistant', 'creating_session'] },
]

const currentStep = computed(() => {
  const index = steps.findIndex((step) => step.phases.includes(props.session.provision_phase || ''))
  return index < 0 ? 0 : index
})

const conversion = computed(() => props.session.document_conversion ?? null)
const countsLabel = computed(() => conversionCountsLabel(conversion.value))
const problemItems = computed(() => conversionProblemItems(conversion.value).slice(0, 8))
const phase = computed(() => conversionPhase(conversion.value))
const isConvertingStep = computed(() => props.session.provision_phase === 'converting')
const showRunningMessage = computed(() => (
  (isConvertingStep.value || phase.value === 'running') && !countsLabel.value
))
const showConversionPanel = computed(() => {
  if (props.session.lifecycle_status === 'failed' || props.session.lifecycle_status === 'deleting') {
    return false
  }
  return Boolean(
    isConvertingStep.value
    || phase.value === 'running'
    || (conversion.value && (
      countsLabel.value
      || problemItems.value.length
      || conversionWarnings.value.length
      || props.session.provision_detail
    )),
  )
})
const showFormatHint = computed(() => (
  isConvertingStep.value || phase.value === 'running'
))
const conversionWarnings = computed(() => conversionWarningsForDisplay(conversion.value, 5))
const showFailedConversionPanel = computed(() => Boolean(
  conversion.value
  && (countsLabel.value || problemItems.value.length || conversion.value.error || conversionWarnings.value.length),
))

function stepState(index: number) {
  if (index < currentStep.value) return 'done'
  if (index === currentStep.value) return 'active'
  return 'pending'
}
</script>

<template>
  <main class="copilot-lifecycle-state">
    <div v-if="session.lifecycle_status === 'failed'" class="copilot-lifecycle-card is-failed">
      <span class="copilot-lifecycle-icon is-failed"><AlertCircle :size="30" /></span>
      <h2>We Couldn't Prepare This Chat</h2>
      <p>Something went wrong while preparing the selected data. Try again, or delete this chat and create a new one.</p>
      <div v-if="showFailedConversionPanel" class="copilot-conversion">
        <p v-if="countsLabel" class="copilot-conversion__counts">{{ countsLabel }}</p>
        <p v-if="conversion?.error" class="copilot-conversion__detail">{{ conversion.error }}</p>
        <ul v-if="problemItems.length" class="copilot-conversion__list">
          <li v-for="(item, index) in problemItems" :key="`${item.name}-${index}`">
            <strong>{{ item.name }}</strong>
            <span>{{ item.reason_label }}</span>
          </li>
        </ul>
        <ul v-if="conversionWarnings.length" class="copilot-conversion__list">
          <li v-for="(warning, index) in conversionWarnings" :key="`${warning.code}-${index}`">
            <span>{{ warning.label || warning.code }}</span>
          </li>
        </ul>
      </div>
      <div class="copilot-lifecycle-actions">
        <ElButton @click="emit('delete')">Delete Chat</ElButton>
        <ElButton type="primary" @click="emit('retry')">Try Again</ElButton>
      </div>
    </div>

    <div v-else-if="session.lifecycle_status === 'deleting'" class="copilot-lifecycle-card">
      <span class="copilot-lifecycle-icon"><LoaderCircle :size="30" class="copilot-lifecycle-spin" /></span>
      <h2>Deleting Chat</h2>
      <p>The chat and its temporary data are being removed.</p>
    </div>

    <div v-else class="copilot-lifecycle-card">
      <span class="copilot-lifecycle-icon"><Sparkles :size="30" /></span>
      <h2>Preparing Your Chat</h2>
      <p>Your selected data is being prepared for AI Copilot.</p>

      <ol class="copilot-lifecycle-steps">
        <li v-for="(step, index) in steps" :key="step.label" :class="`is-${stepState(index)}`">
          <span>
            <Check v-if="stepState(index) === 'done'" :size="14" />
            <LoaderCircle v-else-if="stepState(index) === 'active'" :size="14" class="copilot-lifecycle-spin" />
            <Circle v-else :size="12" />
          </span>
          {{ step.label }}
        </li>
      </ol>

      <div v-if="showConversionPanel" class="copilot-conversion">
        <p v-if="session.provision_detail" class="copilot-conversion__detail">{{ session.provision_detail }}</p>
        <p v-if="conversion?.progress_message" class="copilot-conversion__detail">{{ conversion.progress_message }}</p>
        <p v-if="showRunningMessage" class="copilot-conversion__detail">{{ t('insight.copilot.documentConversionRunning') }}</p>
        <p v-if="countsLabel" class="copilot-conversion__counts">{{ countsLabel }}</p>
        <ul v-if="problemItems.length" class="copilot-conversion__list">
          <li v-for="(item, index) in problemItems" :key="`${item.name}-${index}`">
            <strong>{{ item.name }}</strong>
            <span>{{ item.reason_label }}</span>
          </li>
        </ul>
        <ul v-if="conversionWarnings.length" class="copilot-conversion__list">
          <li v-for="(warning, index) in conversionWarnings" :key="`${warning.code}-${index}`">
            <span>{{ warning.label || warning.code }}</span>
          </li>
        </ul>
        <p v-if="showFormatHint" class="copilot-conversion__hint">{{ t('insight.copilot.documentFormatHint') }}</p>
      </div>

      <small>You can leave this page. Preparation will continue in the background.</small>
    </div>
  </main>
</template>

<style scoped>
.copilot-lifecycle-state { display: flex; min-height: 0; flex: 1; align-items: center; justify-content: center; padding: 40px 24px; overflow-y: auto; background: var(--color-card-bg); }
.copilot-lifecycle-card { display: flex; width: min(520px, 100%); flex-direction: column; align-items: center; padding: 34px 36px; border: 1px solid var(--color-border-light); border-radius: 14px; background: var(--color-card-bg); box-shadow: 0 14px 34px rgba(29, 33, 41, .07); text-align: center; }
.copilot-lifecycle-icon { display: inline-flex; width: 58px; height: 58px; align-items: center; justify-content: center; margin-bottom: 18px; border-radius: 16px; background: color-mix(in srgb, var(--color-primary) 10%, var(--color-card-bg)); color: var(--color-primary); animation: copilot-lifecycle-breathe 2.2s ease-in-out infinite; }
.copilot-lifecycle-icon.is-failed { background: #fef3f2; color: #d92d20; animation: none; }
.copilot-lifecycle-card h2 { margin: 0; color: var(--color-text-title); font-size: 20px; font-weight: 650; }
.copilot-lifecycle-card > p { max-width: 430px; margin: 9px 0 0; color: var(--color-text-tertiary); font-size: 13px; line-height: 1.6; }
.copilot-lifecycle-steps { display: grid; width: min(360px, 100%); gap: 13px; margin: 26px 0 22px; padding: 20px 22px; border-radius: 10px; background: var(--color-grey-2); list-style: none; text-align: left; }
.copilot-lifecycle-steps li { display: flex; align-items: center; gap: 10px; color: var(--color-text-disabled); font-size: 13px; }
.copilot-lifecycle-steps li > span { display: inline-flex; width: 20px; height: 20px; flex-shrink: 0; align-items: center; justify-content: center; }
.copilot-lifecycle-steps li.is-done { color: var(--color-text-secondary); }.copilot-lifecycle-steps li.is-done > span { border-radius: 999px; background: #ecfdf3; color: #039855; }
.copilot-lifecycle-steps li.is-active { color: var(--color-text-title); font-weight: 600; }.copilot-lifecycle-steps li.is-active > span { color: var(--color-primary); }
.copilot-lifecycle-card small { color: var(--color-text-tertiary); font-size: 12px; }
.copilot-lifecycle-actions { display: flex; justify-content: center; gap: 10px; margin-top: 24px; }
.copilot-lifecycle-spin { animation: copilot-lifecycle-spin .9s linear infinite; }
.copilot-conversion { width: min(400px, 100%); margin: 0 0 18px; padding: 14px 16px; border-radius: 10px; background: var(--color-grey-2); text-align: left; }
.copilot-conversion__detail { margin: 0 0 8px; color: var(--color-text-secondary); font-size: 12px; line-height: 1.5; }
.copilot-conversion__counts { margin: 0 0 8px; color: var(--color-text-title); font-size: 12px; font-weight: 600; }
.copilot-conversion__list { display: grid; gap: 8px; margin: 0; padding: 0; list-style: none; }
.copilot-conversion__list li { display: grid; gap: 2px; }
.copilot-conversion__list strong { overflow-wrap: anywhere; color: var(--color-text-title); font-size: 12px; font-weight: 600; }
.copilot-conversion__list span { color: var(--color-text-tertiary); font-size: 11px; line-height: 1.4; }
.copilot-conversion__hint { margin: 10px 0 0; color: var(--color-text-tertiary); font-size: 11px; line-height: 1.45; }
@keyframes copilot-lifecycle-spin { to { transform: rotate(360deg); } }
@keyframes copilot-lifecycle-breathe { 50% { transform: translateY(-3px) scale(1.04); box-shadow: 0 10px 26px color-mix(in srgb, var(--color-primary) 20%, transparent); } }
</style>
