/**
 * Copy text with a fallback for HTTP deployments and browsers where the
 * asynchronous Clipboard API is unavailable or denied.
 */
export async function copyTextToClipboard(text: string): Promise<void> {
  if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text)
      return
    } catch {
      // Keep going: execCommand still works in some restricted environments.
    }
  }

  if (typeof document === 'undefined' || !document.body || typeof document.execCommand !== 'function') {
    throw new Error('Clipboard is unavailable')
  }

  const textarea = document.createElement('textarea')
  textarea.value = text
  textarea.readOnly = true
  textarea.setAttribute('aria-hidden', 'true')
  textarea.style.position = 'fixed'
  textarea.style.top = '0'
  textarea.style.left = '-9999px'
  textarea.style.opacity = '0'
  document.body.appendChild(textarea)

  try {
    textarea.focus()
    textarea.select()
    textarea.setSelectionRange(0, textarea.value.length)
    if (!document.execCommand('copy')) throw new Error('Copy command failed')
  } finally {
    textarea.remove()
  }
}
