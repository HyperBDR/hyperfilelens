<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElInput } from 'element-plus'

const props = withDefaults(defineProps<{
  keyword: string
  hint?: string
  placeholder?: string
  disabled?: boolean
}>(), {
  hint: '',
  placeholder: '',
  disabled: false,
})

const model = defineModel<string>({ default: '' })

const emit = defineEmits<{
  confirm: []
}>()

const { t } = useI18n()

const matched = computed(() => model.value === props.keyword)
const validationError = computed(() => {
  const value = model.value
  if (!value || matched.value) return ''
  if (value.trim() !== value) {
    return t('common.keywordConfirmWhitespaceError')
  }
  if (value.toUpperCase() === props.keyword.toUpperCase()) {
    return t('common.keywordConfirmCaseError', { keyword: props.keyword })
  }
  return t('common.keywordConfirmMismatchError', { keyword: props.keyword })
})

function confirm() {
  if (matched.value && !props.disabled) emit('confirm')
}
</script>

<template>
  <div class="exact-keyword-confirm">
    <p class="exact-keyword-confirm__hint">
      {{ hint || t('common.keywordConfirmDefaultHint', { keyword }) }}
    </p>
    <p class="exact-keyword-confirm__rules">
      {{ t('common.keywordConfirmRules') }}
    </p>
    <ElInput
      v-model="model"
      class="exact-keyword-confirm__input"
      :class="{ 'is-error': validationError }"
      :placeholder="placeholder || keyword"
      :disabled="disabled"
      :validate-event="false"
      autocomplete="off"
      autocapitalize="off"
      autocorrect="off"
      spellcheck="false"
      autofocus
      @keyup.enter="confirm"
    />
    <p
      v-if="validationError"
      class="exact-keyword-confirm__error"
      role="alert"
    >
      {{ validationError }}
    </p>
  </div>
</template>

<style scoped>
.exact-keyword-confirm {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.exact-keyword-confirm__hint,
.exact-keyword-confirm__rules,
.exact-keyword-confirm__error {
  margin: 0;
  font-size: 13px;
  line-height: 1.5;
}

.exact-keyword-confirm__hint {
  color: var(--color-text-secondary, #475569);
  font-weight: 600;
}

.exact-keyword-confirm__rules {
  color: var(--color-text-tertiary, #64748b);
}

.exact-keyword-confirm__error {
  color: var(--el-color-danger);
}

.exact-keyword-confirm__input.is-error :deep(.el-input__wrapper) {
  box-shadow: 0 0 0 1px var(--el-color-danger) inset;
}
</style>
