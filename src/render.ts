import { Page, PageMetadata } from './types';

function escapeHtml(value: string): string {
  return value.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

export function renderPage(metadata: PageMetadata, html: string): string {
  const date = metadata.date ? `<time datetime="${escapeHtml(metadata.date)}">${escapeHtml(metadata.date)}</time>` : '';
  const tags = metadata.tags.length ? `<ul class="tags">${metadata.tags.map((tag) => `<li>${escapeHtml(tag)}</li>`).join('')}</ul>` : '';
  return `<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>${escapeHtml(metadata.title)}</title></head>
<body><main><article><h1>${escapeHtml(metadata.title)}</h1>${date}${tags}${html}</article></main></body>
</html>`;
}

export function renderIndex(pages: Page[]): string {
  const items = pages.map((page) => {
    const date = page.metadata.date ? ` <time datetime="${escapeHtml(page.metadata.date)}">${escapeHtml(page.metadata.date)}</time>` : '';
    return `<li><a href="${encodeURI(page.outputPath)}">${escapeHtml(page.metadata.title)}</a>${date}</li>`;
  }).join('');
  return `<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Pages</title></head>
<body><main><h1>Pages</h1><ul>${items}</ul></main></body>
</html>`;
}
