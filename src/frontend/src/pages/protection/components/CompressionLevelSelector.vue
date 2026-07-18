<script setup lang="ts">
import type { Component } from 'vue'
import HflHelpTip from '../../../components/HflHelpTip.vue'
import { parseCompressionLevel, type CompressionLevel } from '../../../lib/protectionBackupConfigApi'

type CompressionLevelOption = {
  value: CompressionLevel
  title: string
  description: string
  tooltip: string
  icon: Component
}

const props = withDefaults(defineProps<{
  modelValue: CompressionLevel | ''
  options: CompressionLevelOption[]
  mode?: 'radio' | 'select'
  clearable?: boolean
  ariaLabel: string
}>(), {
  mode: 'radio',
  clearable: false,
})

const emit = defineEmits<{
  'update:modelValue': [value: CompressionLevel | '']
}>()

function emitValue(value: unknown) {
  if (props.mode === 'select' && (value === '' || value == null)) {
    emit('update:modelValue', '')
    return
  }
  emit('update:modelValue', parseCompressionLevel(value))
}

function compressionTitle(level: CompressionLevel) {
  return props.options.find((option) => option.value === level)?.title ?? ''
}

function compressionIcon(level: CompressionLevel) {
  return props.options.find((option) => option.value === level)?.icon
}
</script>

<template>
  <el-select
    v-if="mode === 'select'"
    :model-value="modelValue"
    :clearable="clearable"
    :placeholder="ariaLabel"
    class="w-full"
    popper-class="batch-compression-select-popper"
    placement="bottom-start"
    :fallback-placements="['bottom-start', 'bottom-end']"
    :aria-label="ariaLabel"
    @update:model-value="emitValue"
  >
    <template #label>
      <span
        v-if="modelValue"
        class="compression-select-label"
      >
        <component
          :is="compressionIcon(modelValue)"
          :size="15"
          aria-hidden="true"
          class="compression-level-icon"
          :class="`compression-level-icon--${modelValue}`"
        />
        <span class="compression-select-label__text">{{ compressionTitle(modelValue) }}</span>
      </span>
    </template>
    <el-option
      v-for="option in options"
      :key="option.value"
      :label="option.title"
      :value="option.value"
    >
      <div class="batch-compression-option">
        <div class="batch-compression-option__head">
          <span class="batch-compression-option__identity">
            <component
              :is="option.icon"
              :size="16"
              aria-hidden="true"
              class="compression-level-icon"
              :class="`compression-level-icon--${option.value}`"
            />
            <span class="batch-compression-option__title">{{ option.title }}</span>
          </span>
          <HflHelpTip
            :content="option.tooltip"
            :aria-label="`${option.title}: ${option.tooltip}`"
            placement="right"
          />
        </div>
        <span class="batch-compression-option__description">{{ option.description }}</span>
      </div>
    </el-option>
  </el-select>

  <el-radio-group
    v-else
    :model-value="modelValue"
    class="create-compression-radio-group hfl-table-no-tooltip"
    :aria-label="ariaLabel"
    @update:model-value="emitValue"
  >
    <div
      v-for="option in options"
      :key="option.value"
      class="create-compression-radio-option"
      :class="{ 'create-compression-radio-option--active': modelValue === option.value }"
    >
      <div class="create-compression-radio-option__head">
        <el-radio :value="option.value">
          <span class="create-compression-radio-option__title">{{ option.title }}</span>
        </el-radio>
        <HflHelpTip
          :content="option.tooltip"
          :aria-label="`${option.title}: ${option.tooltip}`"
          placement="top"
        />
      </div>
      <p class="create-compression-radio-option__description">
        {{ option.description }}
      </p>
    </div>
  </el-radio-group>
</template>

<style scoped>
.compression-select-label,
.batch-compression-option__identity {
  display: inline-flex;
  min-width: 0;
  align-items: center;
  gap: 7px;
}

.compression-select-label {
  max-width: 100%;
}

.compression-select-label__text {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.compression-level-icon {
  flex: 0 0 auto;
  color: rgb(100 116 139);
}

.compression-level-icon--balanced {
  color: var(--color-primary);
}

.compression-level-icon--high {
  color: rgb(180 83 9);
}

.create-compression-radio-group {
  display: grid;
  width: 100%;
  min-width: 340px;
}

.create-compression-radio-option {
  display: grid;
  min-width: 0;
  min-height: 54px;
  align-content: center;
  gap: 2px;
  padding: 7px 0;
  border-bottom: 1px solid rgb(226 232 240);
}

.create-compression-radio-option:last-child {
  border-bottom: 0;
}

.create-compression-radio-option__head {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 4px;
}

.create-compression-radio-option__head :deep(.el-radio) {
  min-width: 0;
  flex: 0 1 auto;
  margin-right: 0;
}

.create-compression-radio-option__head :deep(.el-radio__label) {
  min-width: 0;
  padding-left: 7px;
  white-space: normal;
}

.create-compression-radio-option__title {
  color: rgb(30 41 59);
  font-size: 13px;
  font-weight: 650;
  line-height: 18px;
}

.create-compression-radio-option--active .create-compression-radio-option__title {
  color: var(--color-primary);
}

.create-compression-radio-option__description {
  min-width: 0;
  margin: 0;
  padding-left: 21px;
  color: rgb(100 116 139);
  font-size: 12px;
  line-height: 1.45;
}

.batch-compression-option {
  display: flex;
  min-width: 280px;
  flex-direction: column;
  gap: 2px;
  padding: 4px 0;
  line-height: 1.35;
}

.batch-compression-option__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.batch-compression-option__title {
  color: var(--el-text-color-primary);
  font-weight: 600;
}

.batch-compression-option__description {
  max-width: 340px;
  overflow-wrap: anywhere;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  white-space: normal;
}

:global(.batch-compression-select-popper .el-select-dropdown__item) {
  height: auto;
  min-height: 52px;
  padding-top: 4px;
  padding-bottom: 4px;
  line-height: normal;
}
</style>
