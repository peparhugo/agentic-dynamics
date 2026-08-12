import fs from 'fs/promises';
import path from 'path';
import { parseFrontmatter, renderMarkdown } from './markdown';
import { Page } from './types';

const MARKDOWN_EXTENSIONS = new Set(['.md', '.markdown']);

export function isMarkdownFile(fileName: string): boolean {
  return MARKDOWN_EXTENSIONS.has(path.extname(fileName).toLowerCase());
}

export function slugFromSource(source: string): string {
  const withoutExt = source.replace(/\.md$/i, '').replace(/\.markdown$/i, '');
  const slug = withoutExt
    .split(/[\\/]+/)
    .map((segment) =>
      segment.replace(/[\s_]+/g, '-').replace(/[^a-zA-Z0-9-]/g, '')
    )
    .join('/');
  return slug.replace(/^-+|-+$/g, '').replace(/\/+/g, '/');
}

export function titleFromSource(source: string): string {
  const slug = slugFromSource(source);
  const name = slug.split('/').pop() ?? slug;
  return name
    .split('-')
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

export async function collectMarkdownFiles(contentDir: string): Promise<string[]> {
  const files: string[] = [];

  async function walk(dir: string, relative: string): Promise<void> {
    const entries = await fs.readdir(dir, { withFileTypes: true });
    entries.sort((a, b) => a.name.localeCompare(b.name));
    for (const entry of entries) {
      const relPath = path.join(relative, entry.name);
      const absPath = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        await walk(absPath, relPath);
      } else if (entry.isFile() && isMarkdownFile(entry.name)) {
        files.push(relPath);
      }
    }
  }

  await walk(contentDir, '');
  return files;
}

export async function buildPage(contentDir: string, source: string): Promise<Page> {
  const absPath = path.join(contentDir, source);
  const raw = await fs.readFile(absPath, 'utf-8');
  const { title, date, tags, template, layout, body } = parseFrontmatter(raw);
  const html = await renderMarkdown(body);

  return {
    slug: slugFromSource(source),
    source,
    title: title ?? titleFromSource(source),
    date,
    tags,
    template,
    layout,
    body,
    html,
  };
}

export function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

export function renderPageHtml(page: Page): string {
  const title = escapeHtml(page.title);
  const date = page.date
    ? `<p class="page-date">${escapeHtml(page.date)}</p>`
    : '';
  const tags = page.tags.length
    ? `<ul class="page-tags">${page.tags
        .map((tag) => `<li class="tag">${escapeHtml(tag)}</li>`)
        .join('')}</ul>`
    : '';

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>${title}</title>
</head>
<body>
  <nav><a href="index.html">&larr; Home</a></nav>
  <article>
    <h1>${title}</h1>
    ${date}
    ${tags}
    <div class="content">
${page.html}
    </div>
  </article>
</body>
</html>
`;
}

function comparePages(a: Page, b: Page): number {
  if (a.date && b.date) {
    const cmp = new Date(b.date).getTime() - new Date(a.date).getTime();
    if (cmp !== 0) return cmp;
  }
  if (a.date && !b.date) return -1;
  if (!a.date && b.date) return 1;
  return a.title.localeCompare(b.title);
}

export function renderIndexHtml(pages: Page[]): string {
  const items = pages
    .slice()
    .sort(comparePages)
    .map((page) => {
      const href = `${page.slug}.html`;
      const date = page.date
        ? `<span class="index-date">${escapeHtml(page.date)}</span>`
        : '';
      const tags = page.tags.length
        ? ` <span class="index-tags">[${page.tags
            .map((tag) => escapeHtml(tag))
            .join(', ')}]</span>`
        : '';
      return `    <li><a href="${escapeHtml(href)}">${escapeHtml(page.title)}</a>${date}${tags}</li>`;
    })
    .join('\n');

  const total = pages.length;
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Index</title>
</head>
<body>
  <h1>Pages</h1>
  ${items.length ? `<ul>\n${items}\n</ul>` : '<p>No pages yet.</p>'}
  <p class="footer">${total} page${total === 1 ? '' : 's'}</p>
</body>
</html>
`;
}
