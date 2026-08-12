import fs from 'fs';
import path from 'path';
import { Page, BuildResult } from './types';
import { parseMarkdown } from './markdown';

export const DEFAULT_CONTENT_DIR = 'content';
export const DEFAULT_OUTPUT_DIR = 'dist';

function escapeHtml(input: string): string {
  return input
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

export function findMarkdownFiles(contentDir: string): string[] {
  const results: string[] = [];
  const walk = (dir: string): void => {
    const entries = fs.readdirSync(dir, { withFileTypes: true });
    for (const entry of entries) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        walk(full);
      } else if (entry.isFile() && /\.mdx?$/i.test(entry.name)) {
        results.push(full);
      }
    }
  };
  walk(contentDir);
  results.sort();
  return results;
}

export function readPages(contentDir: string): Page[] {
  const files = findMarkdownFiles(contentDir);
  return files.map((file) =>
    parseMarkdown(fs.readFileSync(file, 'utf8'), path.relative(contentDir, file))
  );
}

export function sortPages(pages: Page[]): Page[] {
  return [...pages].sort((a, b) => {
    const da = a.date ? new Date(a.date).getTime() : 0;
    const db = b.date ? new Date(b.date).getTime() : 0;
    if (da !== db) return db - da;
    return a.title.localeCompare(b.title);
  });
}

function renderTags(tags: string[]): string {
  return tags
    .map(
      (tag) =>
        `<a class="tag" href="?tag=${encodeURIComponent(tag)}">${escapeHtml(tag)}</a>`
    )
    .join('');
}

export function renderPage(page: Page): string {
  const dateHtml = page.date
    ? `<time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>`
    : '';
  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${escapeHtml(page.title)}</title>
</head>
<body>
<nav><a href="./index.html">Home</a></nav>
<main>
<article>
<h1>${escapeHtml(page.title)}</h1>
${dateHtml}
<div class="tags">${renderTags(page.tags)}</div>
<div class="content">
${page.html}
</div>
</article>
</main>
</body>
</html>
`;
}

export function renderIndex(pages: Page[]): string {
  const items = pages
    .map((page) => {
      const dateHtml = page.date
        ? `<time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>`
        : '';
      const tagsHtml = page.tags
        .map((tag) => `<span class="tag">${escapeHtml(tag)}</span>`)
        .join(' ');
      return `    <li class="page">
      <h2><a href="${escapeHtml(page.slug)}.html">${escapeHtml(page.title)}</a></h2>
      <p class="meta">${dateHtml} ${tagsHtml}</p>
      <p class="excerpt">${escapeHtml(page.excerpt)}</p>
    </li>`;
    })
    .join('\n');
  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Home</title>
</head>
<body>
<main>
<h1>Pages</h1>
<ul class="pages">
${items}
</ul>
</main>
</body>
</html>
`;
}

export function buildSite(contentDir: string, outputDir: string): BuildResult {
  if (!fs.existsSync(contentDir)) {
    throw new Error(`content directory not found: ${contentDir}`);
  }
  const pages = sortPages(readPages(contentDir));
  fs.mkdirSync(outputDir, { recursive: true });

  const files: string[] = [];
  for (const page of pages) {
    const name = `${page.slug}.html`;
    fs.writeFileSync(path.join(outputDir, name), renderPage(page), 'utf8');
    files.push(name);
  }

  fs.writeFileSync(path.join(outputDir, 'index.html'), renderIndex(pages), 'utf8');
  files.push('index.html');

  return { pages: pages.length, outputDir, files };
}
