<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { MapPin } from 'lucide-vue-next'
import { useI18n } from 'vue-i18n'
import S3PlatformBrandIcon from '../../../components/S3PlatformBrandIcon.vue'
import type { StorageProviderConfig, StorageProviderRegion } from '../../../lib/storageProviderCatalogApi'

const props = defineProps<{ providers: StorageProviderConfig[] }>()

const { t } = useI18n()
const expandedProviderIds = ref<string[]>([])

const groupedProviders = computed(() => props.providers.map((provider) => {
  const groups = new Map<string, { label: string; regions: StorageProviderRegion[] }>()

  for (const region of provider.regions) {
    const key = region.region_group || region.region_group_en || region.id
    const group = groups.get(key) || {
      label: region.region_group_en || region.region_group || key,
      regions: [],
    }
    group.regions.push(region)
    groups.set(key, group)
  }

  return {
    ...provider,
    groups: Array.from(groups, ([key, group]) => ({ key, ...group })),
  }
}))

watch(
  () => props.providers.map((provider) => provider.id),
  (providerIds) => {
    expandedProviderIds.value = [...providerIds]
  },
  { immediate: true },
)
</script>

<template>
  <section
    class="provider-import-region-review"
    :aria-label="t('platformOps.storageProviders.importedRegions')"
  >
    <el-empty
      v-if="!groupedProviders.length"
      :description="t('platformOps.storageProviders.noImportedRegions')"
      :image-size="64"
    />

    <el-collapse
      v-else
      v-model="expandedProviderIds"
      class="provider-import-region-review__providers"
    >
      <el-collapse-item
        v-for="provider in groupedProviders"
        :key="provider.id"
        :name="provider.id"
      >
        <template #title>
          <div class="provider-import-region-review__provider-title">
            <div class="provider-import-region-review__provider-identity">
              <span
                class="provider-import-region-review__provider-logo"
                aria-hidden="true"
              >
                <S3PlatformBrandIcon
                  :platform="provider.id"
                  :size="26"
                  alt=""
                  icon-class="provider-import-region-review__provider-logo-image"
                  lucide-class="provider-import-region-review__provider-logo-fallback"
                />
              </span>
              <div class="provider-import-region-review__provider-copy">
                <strong>{{ provider.display_name || provider.id }}</strong>
                <code>{{ provider.id }}</code>
              </div>
            </div>
            <span class="provider-import-region-review__provider-count">
              <MapPin
                :size="14"
                aria-hidden="true"
              />
              {{ t('platformOps.storageProviders.regionCount', { count: provider.regions.length }) }}
            </span>
          </div>
        </template>

        <div
          v-if="provider.groups.length"
          class="provider-import-region-review__groups"
        >
          <section
            v-for="group in provider.groups"
            :key="group.key"
            class="provider-import-region-review__group"
          >
            <header>
              <h3>{{ group.label }}</h3>
              <span>{{ t('platformOps.storageProviders.regionCount', { count: group.regions.length }) }}</span>
            </header>
            <div class="provider-import-region-review__regions">
              <article
                v-for="region in group.regions"
                :key="region.id"
              >
                <strong>{{ region.display_name || region.id }}</strong>
                <code>{{ region.id }}</code>
              </article>
            </div>
          </section>
        </div>

        <el-empty
          v-else
          :description="t('platformOps.storageProviders.noImportedRegions')"
          :image-size="44"
        />
      </el-collapse-item>
    </el-collapse>
  </section>
</template>

<style scoped>
.provider-import-region-review {
  width: 100%;
}

.provider-import-region-review__providers {
  border-top: 0;
  border-bottom: 0;
}

.provider-import-region-review__providers :deep(.el-collapse-item) {
  margin-bottom: 12px;
  overflow: hidden;
  border: 1px solid var(--color-border-light, #e6e7ee);
  border-radius: 10px;
  background: #fff;
}

.provider-import-region-review__providers :deep(.el-collapse-item:last-child) {
  margin-bottom: 0;
}

.provider-import-region-review__providers :deep(.el-collapse-item__header) {
  height: auto;
  min-height: 70px;
  padding: 11px 16px;
  border-bottom: 0;
  background: linear-gradient(135deg, color-mix(in srgb, var(--color-primary, #6d5ef6) 7%, #fff), #fafbfe 72%);
  transition: background .18s ease, box-shadow .18s ease;
}

.provider-import-region-review__providers :deep(.el-collapse-item__header:hover) {
  background: linear-gradient(135deg, color-mix(in srgb, var(--color-primary, #6d5ef6) 10%, #fff), #f8f9fd 72%);
}

.provider-import-region-review__providers :deep(.el-collapse-item.is-active .el-collapse-item__header) {
  box-shadow: inset 0 -1px 0 var(--color-border-light, #e6e7ee);
}

.provider-import-region-review__providers :deep(.el-collapse-item__wrap) {
  border-bottom: 0;
}

.provider-import-region-review__providers :deep(.el-collapse-item__content) {
  padding: 0;
}

.provider-import-region-review__provider-title {
  display: flex;
  min-width: 0;
  flex: 1;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding-right: 12px;
}

.provider-import-region-review__provider-identity {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 12px;
}

.provider-import-region-review__provider-logo {
  display: inline-flex;
  width: 40px;
  height: 40px;
  flex: 0 0 40px;
  align-items: center;
  justify-content: center;
  border: 1px solid color-mix(in srgb, var(--color-primary, #6d5ef6) 14%, var(--color-border-light, #e6e7ee));
  border-radius: 10px;
  background: rgb(255 255 255 / 92%);
  box-shadow: 0 2px 8px rgb(29 33 41 / 6%);
}

.provider-import-region-review__provider-logo :deep(img) {
  display: block;
  max-width: 26px;
  max-height: 26px;
  object-fit: contain;
}

.provider-import-region-review__provider-logo :deep(svg) {
  color: var(--color-primary, #6d5ef6);
}

.provider-import-region-review__provider-copy {
  display: grid;
  min-width: 0;
  gap: 2px;
}

.provider-import-region-review__provider-title strong {
  overflow: hidden;
  color: var(--color-text-title, #1c1c26);
  font-size: 14px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.provider-import-region-review__provider-title code,
.provider-import-region-review__group code {
  color: var(--color-text-secondary, #777786);
  font: 11px ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}

.provider-import-region-review__provider-count,
.provider-import-region-review__group header span {
  flex: 0 0 auto;
  color: var(--color-text-secondary, #777786);
  font-size: 12px;
  font-weight: 500;
}

.provider-import-region-review__provider-count {
  display: inline-flex;
  min-width: max-content;
  align-items: center;
  gap: 5px;
  font-size: 11px;
  letter-spacing: .01em;
}

.provider-import-region-review__provider-count svg {
  color: color-mix(in srgb, var(--color-primary, #6d5ef6) 62%, var(--color-text-secondary, #777786));
}

.provider-import-region-review__groups {
  display: grid;
  gap: 18px;
  padding: 18px;
}

.provider-import-region-review__group {
  min-width: 0;
}

.provider-import-region-review__group header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}

.provider-import-region-review__group h3 {
  margin: 0;
  color: var(--color-text-title, #1c1c26);
  font-size: 12px;
  font-weight: 650;
}

.provider-import-region-review__regions {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(210px, 1fr));
  gap: 8px;
}

.provider-import-region-review__regions article {
  display: grid;
  min-width: 0;
  gap: 3px;
  padding: 10px 12px;
  border: 1px solid var(--color-border-light, #ededf3);
  border-radius: 8px;
  background: var(--color-fill-light, #fafafe);
}

.provider-import-region-review__regions strong {
  overflow: hidden;
  color: var(--color-text-title, #1c1c26);
  font-size: 12px;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@media (max-width: 720px) {
  .provider-import-region-review__regions {
    grid-template-columns: 1fr;
  }

  .provider-import-region-review__groups {
    padding: 14px;
  }

  .provider-import-region-review__provider-title {
    gap: 10px;
  }

  .provider-import-region-review__provider-identity {
    gap: 9px;
  }

  .provider-import-region-review__provider-logo {
    width: 36px;
    height: 36px;
    flex-basis: 36px;
  }
}
</style>
