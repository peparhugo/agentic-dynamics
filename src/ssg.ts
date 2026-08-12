import { promises as fs } from 'fs';
import * as path from 'path';
import { marked } from 'marked';
import matter from 'gray-matter';

import type { BuildOptions, Page } from './types';
import {
  loadTemplateEngine,
  renderIndexWithTemplates,
  renderPageWithTemplates,
  type FallbackRenderers,
} from './templates';

function slugify(name: string): string {
  return name
    .replace(/\.md$/i, '')
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

function normalizeTags(tags: unknown): string[] {
  if (Array.isArray(tags)) {
    return tags.map((tag) => String(tag)).filter((tag) => tag.length > 0);
  }
  if (typeof tags === 'string') {
    return tags
      .split(',')
      .map((tag) => tag.trim())
      .filter((tag) => tag.length > 0);
  }
  return [];
}

export function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

export function pagePath(page: Page): string {
  return `${page.slug}.html`;
}

export async function listMarkdownFiles(contentDir: string): Promise<string[]> {
  const entries = await fs.readdir(contentDir, { withFileTypes: true });
  const files: string[] = [];
  for (const entry of entries) {
    const fullPath = path.join(contentDir, entry.name);
    if (entry.isDirectory()) {
      files.push(...(await listMarkdownFiles(fullPath)));
    } else if (entry.isFile() && /\.md$/i.test(entry.name)) {
      files.push(fullPath);
    }
  }
  return files.sort();
}

export async function parseMarkdownFile(filePath: string): Promise<Page> {
  const raw = await fs.readFile(filePath, 'utf8');
  const parsed = matter(raw);
  const frontmatter = parsed.data ?? {};
  const baseName = path.basename(filePath);
  const slug = slugify(baseName);
  const title =
    typeof frontmatter.title === 'string' && frontmatter.title.trim().length > 0
      ? frontmatter.title.trim()
      : baseName.replace(/\.md$/i, '');
  const rawDate = frontmatter.date;
  const date =
    typeof rawDate === 'string' && rawDate.trim().length > 0
      ? rawDate.trim()
      : rawDate instanceof Date && !isNaN(rawDate.getTime())
        ? rawDate.toISOString().slice(0, 10)
        : undefined;
  const template =
    typeof frontmatter.template === 'string' && frontmatter.template.trim().length > 0
      ? frontmatter.template.trim()
      : undefined;
  const layout =
    typeof frontmatter.layout === 'string' && frontmatter.layout.trim().length > 0
      ? frontmatter.layout.trim()
      : undefined;
  const html = await marked.parse(parsed.content);
  return {
    slug,
    title,
    date,
    tags: normalizeTags(frontmatter.tags),
    content: parsed.content,
    html,
    template,
    layout,
    data: frontmatter,
  };
}

export function renderDocument(page: Page, content: string): string {
  const dateHtml = page.date
    ? `<p class="date"><time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time></p>`
    : '';
  const tagsHtml =
    page.tags.length > 0
      ? `<p class="tags">${page.tags
          .map((tag) => `<span class="tag">${escapeHtml(tag)}</span>`)
          .join(' ')}</p>`
      : '';
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>${escapeHtml(page.title)}</title>
</head>
<body>
  <header>
    <nav><a href="index.html">Home</a></nav>
    <h1>${escapeHtml(page.title)}</h1>
    ${dateHtml}
  </header>
  <main>
${content}
${tagsHtml}
  </main>
</body>
</html>
`;
}

export function renderPage(page: Page): string {
  return renderDocument(page, page.html);
}

export function renderIndexItems(pages: Page[]): string {
  return [...pages]
    .sort((a, b) => (b.date ?? '').localeCompare(a.date ?? ''))
    .map((page) => {
      const date = page.date
        ? ` <time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>`
        : '';
      const tags =
        page.tags.length > 0
          ? ` <span class="tags">${page.tags.map((tag) => escapeHtml(tag)).join(', ')}</span>`
          : '';
      return `    <li><a href="${pagePath(page)}">${escapeHtml(page.title)}</a>${date}${tags}</li>`;
    })
    .join('\n');
}

export function renderIndexBody(pages: Page[]): string {
  return `    <ul>\n${renderIndexItems(pages)}\n    </ul>`;
}

export function renderIndex(pages: Page[]): string {
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Index</title>
</head>
<body>
  <header>
    <h1>Index</h1>
  </header>
  <main>
${renderIndexBody(pages)}
  </main>
</body>
</html>
`;
}

export async function build(options: BuildOptions): Promise<Page[]> {
  const files = await listMarkdownFiles(options.contentDir);
  const pages: Page[] = [];
  for (const file of files) {
    pages.push(await parseMarkdownFile(file));
  }
  await fs.mkdir(options.outputDir, { recursive: true });
  const engine = await loadTemplateEngine(options.templateDir ?? 'templates');
  const fallbacks: FallbackRenderers = {
    document: renderDocument,
    indexBody: renderIndexBody,
    indexDocument: renderIndex,
  };
  const writes: Promise<void>[] = [
    fs.writeFile(
      path.join(options.outputDir, 'index.html'),
      engine ? renderIndexWithTemplates(pages, engine, fallbacks) : renderIndex(pages),
      'utf8'
    ),
  ];
  for (const page of pages) {
    const html = engine ? renderPageWithTemplates(page, engine, fallbacks) : renderPage(page);
    writes.push(fs.writeFile(path.join(options.outputDir, pagePath(page)), html, 'utf8'));
  }
  await Promise.all(writes);
  return pages;
}
