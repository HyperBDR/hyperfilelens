import type { LensIngestPolicy } from './lensApi'

export const DEFAULT_LENS_INGEST_POLICY: LensIngestPolicy = {
  document: false,
  embedded_image: false,
  image: false,
  document_model_ref: null,
  vision_model_ref: null,
  max_images: 100,
  max_file_size_mb: 100,
  max_pages: 500,
  pdf_extract_images: true,
  pdf_extract_images_on_text_pages: false,
  pdf_render_scanned_pages: false,
  pdf_max_pages: 30,
  pdf_max_images_per_page: 3,
  pdf_render_dpi: 144,
  pdf_min_text_chars: 30,
  pdf_min_image_area_ratio: 0.08,
}

export function defaultLensIngestPolicy(): LensIngestPolicy {
  return { ...DEFAULT_LENS_INGEST_POLICY }
}

function positiveInt(value: unknown, fallback: number): number {
  const n = Number(value)
  return Number.isFinite(n) && n > 0 ? Math.trunc(n) : fallback
}

function ratio(value: unknown, fallback: number): number {
  const n = Number(value)
  if (!Number.isFinite(n) || n <= 0 || n > 1) return fallback
  return n
}

export function normalizeLensIngestPolicy(raw?: Partial<LensIngestPolicy> | null): LensIngestPolicy {
  const base = defaultLensIngestPolicy()
  if (!raw || typeof raw !== 'object') return base

  const policy: LensIngestPolicy = {
    ...base,
    document: raw.document === true,
    embedded_image: raw.embedded_image === true,
    image: raw.image === true,
    document_model_ref: raw.document_model_ref ? String(raw.document_model_ref) : null,
    vision_model_ref: raw.vision_model_ref ? String(raw.vision_model_ref) : null,
    max_images: positiveInt(raw.max_images, base.max_images),
    max_file_size_mb: positiveInt(raw.max_file_size_mb, base.max_file_size_mb),
    max_pages: positiveInt(raw.max_pages, base.max_pages),
    pdf_extract_images: raw.pdf_extract_images !== false,
    pdf_extract_images_on_text_pages: raw.pdf_extract_images_on_text_pages === true,
    pdf_render_scanned_pages: raw.pdf_render_scanned_pages === true,
    pdf_max_pages: positiveInt(raw.pdf_max_pages, base.pdf_max_pages),
    pdf_max_images_per_page: positiveInt(raw.pdf_max_images_per_page, base.pdf_max_images_per_page),
    pdf_render_dpi: positiveInt(raw.pdf_render_dpi, base.pdf_render_dpi),
    pdf_min_text_chars: positiveInt(raw.pdf_min_text_chars, base.pdf_min_text_chars),
    pdf_min_image_area_ratio: ratio(raw.pdf_min_image_area_ratio, base.pdf_min_image_area_ratio),
  }

  if (policy.embedded_image && !policy.document) {
    policy.embedded_image = false
  }

  return policy
}
