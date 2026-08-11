import fs from 'fs';
import path from 'path';
import { Page } from './types';

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function renderLayout(title: string, body: string): string {
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${escapeHtml(title)}</title>
</head>
<body>
  ${body}
</body>
</html>`;
}

function renderPage(page: Page): string {
  const { title, date, tags } = page.frontmatter;
  const tagsHtml = tags.length
    ? `<p>Tags: ${escapeHtml(tags.join(', '))}</p>`
    : '';
  const dateHtml = date ? `<p>Date: ${escapeHtml(date)}</p>` : '';

  const body = `<h1>${escapeHtml(title)}</h1>
${dateHtml}
${tagsHtml}
${page.html}
<p><a href="index.html">Back to index</a></p>`;

  return renderLayout(title, body);
}

function renderIndex(pages: Page[]): string {
  const items = pages
    .map(
      (page) =>
        `<li><a href="${escapeHtml(page.slug)}.html">${escapeHtml(page.frontmatter.title)}</a></li>`
    )
    .join('\n');

  const body = `<h1>Site Index</h1>
<ul>
${items}
</ul>`;

  return renderLayout('Site Index', body);
}

export function generateSite(pages: Page[], outputDir: string): void {
  const resolved = path.resolve(outputDir);
  fs.mkdirSync(resolved, { recursive: true });

  for (const page of pages) {
    const html = renderPage(page);
    fs.writeFileSync(path.join(resolved, `${page.slug}.html`), html, 'utf-8');
  }

  const indexHtml = renderIndex(pages);
  fs.writeFileSync(path.join(resolved, 'index.html'), indexHtml, 'utf-8');
}
