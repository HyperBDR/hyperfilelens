// @vitest-environment jsdom

import { defineComponent } from 'vue'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { describe, expect, it } from 'vitest'
import { en } from '../../../locales/en'
import type { ProviderDiff, ProviderImportPreview, StorageProviderRegion } from '../../../lib/storageProviderCatalogApi'
import ProviderDiffDialog from './ProviderDiffDialog.vue'

const ElDialogStub = defineComponent({
  props: { modelValue: Boolean },
  emits: ['update:modelValue'],
  template: `
    <section v-if="modelValue" class="dialog-stub">
      <header><slot name="header" /></header>
      <slot />
      <footer><slot name="footer" /></footer>
    </section>
  `,
})

const stubs = {
  ElDialog: ElDialogStub,
  ElTag: defineComponent({ template: '<span class="tag-stub"><slot /></span>' }),
  ElButton: defineComponent({
    emits: ['click'],
    template: '<button type="button" @click="$emit(\'click\')"><slot /></button>',
  }),
  ElEmpty: defineComponent({
    props: { description: String },
    template: '<div class="empty-stub">{{ description }}</div>',
  }),
  ElSelect: defineComponent({ template: '<div class="select-stub"><slot /></div>' }),
  ElOption: defineComponent({ template: '<span />' }),
}

function region(id: string): StorageProviderRegion {
  return {
    id,
    display_name: id,
    region_group: 'asia_pacific',
    region_group_en: 'Asia Pacific',
    external_endpoint: `${id}.external.example.com`,
    internal_endpoint: `${id}.internal.example.com`,
    driver: 's3',
    s3_url_style: 'virtual_hosted',
    use_tls: true,
  }
}

function provider(overrides: Partial<ProviderDiff> & Pick<ProviderDiff, 'provider_id' | 'change_type'>): ProviderDiff {
  return {
    provider_changes: [],
    added_regions: [],
    removed_regions: [],
    modified_regions: [],
    high_risk_changes: [],
    persistence_action: 'upsert_override',
    ...overrides,
  }
}

const preview: ProviderImportPreview = {
  schema_version: 1,
  input_checksum: 'checksum',
  target_provider_ids: ['unchanged', 'modified', 'added'],
  unchanged_target_provider_ids: ['unchanged'],
  skipped_provider_ids: ['not-imported'],
  high_risk_confirmation_ids: ['risk-1'],
  providers: [
    provider({ provider_id: 'unchanged', change_type: 'unchanged' }),
    provider({
      provider_id: 'modified',
      change_type: 'modified',
      provider_changes: [{ path: 'enabled', before: true, after: false }],
      removed_regions: [region('removed-region')],
      modified_regions: [{
        region_id: 'changed-region',
        changes: [{ path: 'external_endpoint', before: 'old.example.com', after: 'new.example.com' }],
      }],
      high_risk_changes: [{ id: 'risk-1', type: 'region_removed', path: 'regions.removed-region' }],
    }),
    provider({
      provider_id: 'added',
      change_type: 'added',
      added_regions: [region('new-region')],
    }),
  ],
}

function render() {
  const i18n = createI18n({
    legacy: false,
    locale: 'en',
    messages: { en },
    missingWarn: false,
    fallbackWarn: false,
  })
  return mount(ProviderDiffDialog, {
    props: { modelValue: true, preview },
    global: { plugins: [i18n], stubs },
  })
}

describe('ProviderDiffDialog', () => {
  it('summarizes the import and selects the first changed Provider', () => {
    const wrapper = render()

    expect(wrapper.text()).toContain('Configuration Diff Preview')
    const addedSummary = wrapper.get('.provider-diff-dialog__summary-card--added')
    const removedSummary = wrapper.get('.provider-diff-dialog__summary-card--removed')
    const modifiedSummary = wrapper.get('.provider-diff-dialog__summary-card--modified')
    expect([addedSummary.get('span').text(), addedSummary.get('strong').text(), addedSummary.get('small').text()])
      .toEqual(['Added', '1', 'Added regions'])
    expect([removedSummary.get('span').text(), removedSummary.get('strong').text(), removedSummary.get('small').text()])
      .toEqual(['Removed', '1', 'Removed regions'])
    expect([modifiedSummary.get('span').text(), modifiedSummary.get('strong').text(), modifiedSummary.get('small').text()])
      .toEqual(['Modified', '1', 'Modified regions'])
    const activeProvider = wrapper.get('.provider-diff-dialog__providers button.is-active')
    expect(activeProvider.text()).toContain('modified')
    expect(wrapper.get('.provider-diff-dialog__details').text()).toContain('old.example.com')
    expect(wrapper.get('.provider-diff-dialog__details').text()).toContain('new.example.com')
    expect(wrapper.find('.provider-diff__group--removed').exists()).toBe(true)
    expect(wrapper.find('.provider-diff__group--modified').exists()).toBe(true)
    expect(wrapper.text()).not.toContain('High-risk')
    expect(wrapper.text()).not.toContain('region_removed')
  })

  it('switches semantic details without changing the import workflow', async () => {
    const wrapper = render()
    const addedButton = wrapper.findAll('.provider-diff-dialog__providers button')
      .find((button) => button.text().includes('added'))

    expect(addedButton).toBeDefined()
    await addedButton!.trigger('click')

    expect(wrapper.get('.provider-diff-dialog__details').text()).toContain('new-region')
    expect(wrapper.get('.provider-diff-dialog__details').text()).toContain('+ Added')
    expect(wrapper.find('.provider-diff__group--added').exists()).toBe(true)

    await wrapper.get('.provider-diff-dialog__content + footer button').trigger('click')
    expect(wrapper.emitted('update:modelValue')).toContainEqual([false])
  })
})
