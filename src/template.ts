import type { Page } from './types';

export function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function renderTags(tags: string[]): string {
  if (tags.length === 0) {
    return '';
  }
  const items = tags
    .map((tag) => `<span class="tag">${escapeHtml(tag)}</span>`)
    .join('');
  return `<div class="tags">${items}</div>`;
}

function renderMeta(page: Page): string {
  const parts: string[] = [];
  if (page.date) {
    parts.push(`<time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>`);
  }
  if (page.tags.length > 0) {
    parts.push(renderTags(page.tags));
  }
  return parts.length > 0 ? `<div class="meta">${parts.join('')}</div>` : '';
}

export function renderPageHtml(page: Page): string {
  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${escapeHtml(page.title)}</title>
<style>
body { font-family: system-ui, -apple-system, sans-serif; max-width: 48rem; margin: 0 auto; padding: 1.5rem; line-height: 1.6; color: #1a1a1a; }
header { margin-bottom: 2rem; }
a { color: #0b5fff; text-decoration: none; }
a:hover { text-decoration: underline; }
.meta { display: flex; gap: 1rem; align-items: center; color: #666; font-size: 0.9rem; margin-bottom: 1.5rem; }
.tags { display: flex; gap: 0.5rem; }
.tag { background: #eef2ff; color: #3b4fd8; padding: 0.15rem 0.5rem; border-radius: 999px; font-size: 0.8rem; }
.content h1 { font-size: 1.6rem; }
</style>
</head>
<body>
<header><a href="index.html">&larr; Home</a></header>
<main>
<article>
<h1>${escapeHtml(page.title)}</h1>
${renderMeta(page)}
<div class="content">
${page.html}
</div>
</article>
</main>
</body>
</html>
`;
}

export function renderIndexHtml(pages: Page[]): string {
  const items = pages
    .map((page) => {
      const href = `${escapeHtml(page.slug)}.html`;
      const date = page.date ? `<time>${escapeHtml(page.date)}</time>` : '';
      return `<li><a href="${href}">${escapeHtml(page.title)}</a> ${date}${renderTags(page.tags)}</li>`;
    })
    .join('\n');

  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Index</title>
<style>
body { font-family: system-ui, -apple-system, sans-serif; max-width: 48rem; margin: 0 auto; padding: 1.5rem; line-height: 1.6; color: #1a1a1a; }
a { color: #0b5fff; text-decoration: none; }
a:hover { text-decoration: underline; }
ul { list-style: none; padding: 0; }
li { display: flex; gap: 1rem; align-items: center; padding: 0.5rem 0; border-bottom: 1px solid #eee; flex-wrap: wrap; }
li time { color: #888; font-size: 0.85rem; }
.tags { display: flex; gap: 0.5rem; }
.tag { background: #eef2ff; color: #3b4fd8; padding: 0.15rem 0.5rem; border-radius: 999px; font-size: 0.8rem; }
</style>
</head>
<body>
<header><h1>Index</h1></header>
<main>
<ul>
${items}
</ul>
</main>
</body>
</html>
`;
}
