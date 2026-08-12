import { readdir, readFile, mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { parseMarkdown, renderMarkdown } from './markdown';
import type { BuildResult, Page } from './types';

export const DEFAULT_CONTENT_DIR = 'content';
export const DEFAULT_OUTPUT_DIR = 'dist';

async function collectMarkdownFiles(dir: string): Promise<string[]> {
  const files: string[] = [];
  const entries = await readdir(dir, { withFileTypes: true });
  for (const entry of entries) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      files.push(...(await collectMarkdownFiles(full)));
    } else if (/\.(md|markdown)$/i.test(entry.name)) {
      files.push(full);
    }
  }
  return files;
}

export function toSlug(relativePath: string): string {
  return relativePath
    .replace(/\.(md|markdown)$/i, '')
    .split(/[\\/]/)
    .map((part) => part.replace(/[^a-zA-Z0-9]+/g, '-').replace(/^-+|-+$/g, ''))
    .filter(Boolean)
    .join('/');
}

function titleFromSlug(slug: string): string {
  const base = slug.split('/').pop() ?? slug;
  return base
    .split('-')
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

function normalizeTags(tags: string | string[] | undefined): string[] {
  if (Array.isArray(tags)) return tags.map(String);
  if (typeof tags === 'string') {
    return tags
      .split(',')
      .map((tag) => tag.trim())
      .filter(Boolean);
  }
  return [];
}

function pageTitle(relativePath: string): string {
  const parsed = path.parse(relativePath);
  return parsed.name
    .split(/[-_\s]+/)
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

export async function loadPages(contentDir: string): Promise<Page[]> {
  const files = await collectMarkdownFiles(contentDir);
  const pages: Page[] = [];

  for (const file of files) {
    const raw = await readFile(file, 'utf8');
    const { data, body } = parseMarkdown(raw);
    const relative = path.relative(contentDir, file);
    const slug = toSlug(relative);

    pages.push({
      title: (data.title && data.title.trim()) || pageTitle(relative),
      date: (data.date && data.date.trim()) || '',
      tags: normalizeTags(data.tags),
      slug,
      source: relative,
      html: renderMarkdown(body),
    });
  }

  pages.sort((a, b) => {
    if (a.date !== b.date) {
      return a.date < b.date ? 1 : -1;
    }
    return a.slug.localeCompare(b.slug);
  });

  return pages;
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

export function renderPage(page: Page): string {
  const tags = page.tags.map((tag) => `<a class="tag" href="#/tags/${escapeHtml(tag)}">${escapeHtml(tag)}</a>`).join(' ');
  const date = page.date ? `<time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : '';

  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>${escapeHtml(page.title)}</title>
</head>
<body>
  <header>
    <a class="back" href="index.html">&larr; Home</a>
    <h1>${escapeHtml(page.title)}</h1>
    ${date ? `<p class="meta">${date}</p>` : ''}
    ${tags ? `<p class="tags">${tags}</p>` : ''}
  </header>
  <main>
${page.html}
  </main>
</body>
</html>
`;
}

export function renderIndex(pages: Page[]): string {
  const items = pages
    .map(
      (page) => `    <li><a href="${escapeHtml(page.slug)}.html">${escapeHtml(page.title)}</a>${page.date ? ` <time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : ''}</li>`,
    )
    .join('\n');

  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Index</title>
</head>
<body>
  <h1>Index</h1>
  <ul class="pages">
${items}
  </ul>
</body>
</html>
`;
}

export async function buildSite(contentDir: string, outputDir: string): Promise<BuildResult> {
  const pages = await loadPages(contentDir);
  const files: string[] = [];

  await mkdir(outputDir, { recursive: true });

  for (const page of pages) {
    const outPath = path.join(outputDir, `${page.slug}.html`);
    await mkdir(path.dirname(outPath), { recursive: true });
    await writeFile(outPath, renderPage(page), 'utf8');
    files.push(outPath);
  }

  const indexPath = path.join(outputDir, 'index.html');
  await writeFile(indexPath, renderIndex(pages), 'utf8');
  files.push(indexPath);

  return { pages, files };
}
