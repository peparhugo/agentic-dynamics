export function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

export function tagSpans(tags: string[]): string {
  return tags.map((tag) => `<span class="tag">${escapeHtml(tag)}</span>`).join(' ');
}

export function dateElement(date: string): string {
  if (!date) return '';
  return `<time datetime="${escapeHtml(date)}">${escapeHtml(date)}</time>`;
}
