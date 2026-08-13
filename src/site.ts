import { promises as fs } from 'node:fs';
import path from 'node:path';
import matter from 'gray-matter';
import { marked } from 'marked';

export interface Page {
  sourcePath: string;
  outputPath: string;
  url: string;
  title: string;
  date?: string;
  tags: string[];
  html: string;
}

export interface BuildOptions {
  contentDir?: string;
  outputDir?: string;
}

function escapeHtml(value: string): string {
  return value.replace(/[&<>"']/g, (character) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  })[character] ?? character);
}

function valueToString(value: unknown): string | undefined {
  if (value === undefined || value === null) return undefined;
  if (value instanceof Date) return value.toISOString().slice(0, 10);
  return String(value);
}

function toTags(value: unknown): string[] {
  if (Array.isArray(value)) return value.map(String);
  if (typeof value === 'string') return value.split(',').map((tag) => tag.trim()).filter(Boolean);
  return [];
}

async function markdownFiles(directory: string): Promise<string[]> {
  const entries = await fs.readdir(directory, { withFileTypes: true });
  const files = await Promise.all(entries.map(async (entry) => {
    const fullPath = path.join(directory, entry.name);
    if (entry.isDirectory()) return markdownFiles(fullPath);
    return /\.md$/i.test(entry.name) ? [fullPath] : [];
  }));
  return files.flat();
}

export function renderPage(page: Page): string {
  const details = [
    page.date ? `<time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : '',
    page.tags.length ? `<p class="tags">${page.tags.map((tag) => `<span>${escapeHtml(tag)}</span>`).join(' ')}</p>` : '',
  ].filter(Boolean).join('\n');

  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>${escapeHtml(page.title)}</title>
</head>
<body>
  <main>
    <a href="/index.html">Home</a>
    <article>
      <h1>${escapeHtml(page.title)}</h1>
      ${details}
      ${page.html}
    </article>
  </main>
</body>
</html>
`;
}

export function renderIndex(pages: Page[]): string {
  const items = pages.map((page) => {
    const date = page.date ? ` <time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : '';
    return `      <li><a href="${escapeHtml(page.url)}">${escapeHtml(page.title)}</a>${date}</li>`;
  }).join('\n');
  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Index</title>
</head>
<body>
  <main>
    <h1>Pages</h1>
    <ul>
${items}
    </ul>
  </main>
</body>
</html>
`;
}

export async function buildSite(options: BuildOptions = {}): Promise<Page[]> {
  const contentDir = path.resolve(options.contentDir ?? './content');
  const outputDir = path.resolve(options.outputDir ?? './dist');
  const files = await markdownFiles(contentDir);
  const pages = await Promise.all(files.map(async (sourcePath) => {
    const parsed = matter(await fs.readFile(sourcePath, 'utf8'));
    const relativePath = path.relative(contentDir, sourcePath);
    const outputPath = path.join(outputDir, relativePath.replace(/\.md$/i, '.html'));
    const fallbackTitle = path.basename(relativePath, path.extname(relativePath));
    const title = valueToString(parsed.data.title) ?? fallbackTitle;
    const date = valueToString(parsed.data.date);
    return {
      sourcePath,
      outputPath,
      url: `/${path.relative(outputDir, outputPath).split(path.sep).join('/')}`,
      title,
      date,
      tags: toTags(parsed.data.tags),
      html: await marked.parse(parsed.content),
    };
  }));

  pages.sort((left, right) => (right.date ?? '').localeCompare(left.date ?? '') || left.title.localeCompare(right.title));
  await fs.rm(outputDir, { recursive: true, force: true });
  await fs.mkdir(outputDir, { recursive: true });
  await Promise.all(pages.map(async (page) => {
    await fs.mkdir(path.dirname(page.outputPath), { recursive: true });
    await fs.writeFile(page.outputPath, renderPage(page), 'utf8');
  }));
  await fs.writeFile(path.join(outputDir, 'index.html'), renderIndex(pages), 'utf8');
  return pages;
}
