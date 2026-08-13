import { existsSync, mkdirSync, readdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { dirname, join, relative, resolve, sep } from 'node:path';
import matter from 'gray-matter';
import { marked } from 'marked';

export interface Page {
  title: string;
  date?: string;
  tags: string[];
  outputPath: string;
  url: string;
  html: string;
}

export interface BuildOptions {
  contentDir?: string;
  outputDir?: string;
}

const escapeHtml = (value: string): string => value.replace(/[&<>"']/g, (character) => ({
  '&': '&amp;',
  '<': '&lt;',
  '>': '&gt;',
  '"': '&quot;',
  "'": '&#39;'
})[character] ?? character);

function markdownFiles(directory: string): string[] {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) return markdownFiles(path);
    return entry.isFile() && /\.md$/i.test(entry.name) ? [path] : [];
  });
}

function toStringArray(value: unknown): string[] {
  if (Array.isArray(value)) return value.map(String);
  if (typeof value === 'string' && value.length > 0) return [value];
  return [];
}

function toDateString(value: unknown): string | undefined {
  if (value === undefined) return undefined;
  if (value instanceof Date) return value.toISOString().slice(0, 10);
  return String(value);
}

function renderPage(page: Page): string {
  const metadata = [
    page.date ? `<time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : '',
    page.tags.length > 0 ? `<p class="tags">${page.tags.map((tag) => `<span>${escapeHtml(tag)}</span>`).join(' ')}</p>` : ''
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
    <article>
      <h1>${escapeHtml(page.title)}</h1>
      ${metadata}
      ${page.html}
    </article>
  </main>
</body>
</html>
`;
}

function renderIndex(pages: Page[]): string {
  const links = pages.map((page) => `      <li><a href="${escapeHtml(page.url)}">${escapeHtml(page.title)}</a>${page.date ? ` <time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : ''}</li>`).join('\n');
  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Pages</title>
</head>
<body>
  <main>
    <h1>Pages</h1>
    <ul>
${links}
    </ul>
  </main>
</body>
</html>
`;
}

export function buildSite(options: BuildOptions = {}): Page[] {
  const contentDir = resolve(options.contentDir ?? 'content');
  const outputDir = resolve(options.outputDir ?? 'dist');
  if (!existsSync(contentDir)) throw new Error(`Content directory does not exist: ${contentDir}`);

  rmSync(outputDir, { recursive: true, force: true });
  mkdirSync(outputDir, { recursive: true });

  const pages = markdownFiles(contentDir).map((file) => {
    const source = readFileSync(file, 'utf8');
    const parsed = matter(source);
    const relativePath = relative(contentDir, file).replace(/\.md$/i, '.html');
    const url = relativePath.split(sep).join('/');
    const date = toDateString(parsed.data.date);
    const title = typeof parsed.data.title === 'string' && parsed.data.title.length > 0
      ? parsed.data.title
      : relativePath.replace(/\.html$/i, '');
    const page: Page = {
      title,
      date,
      tags: toStringArray(parsed.data.tags),
      outputPath: join(outputDir, relativePath),
      url,
      html: marked.parse(parsed.content)
    };
    mkdirSync(dirname(page.outputPath), { recursive: true });
    writeFileSync(page.outputPath, renderPage(page), 'utf8');
    return page;
  }).sort((left, right) => left.title.localeCompare(right.title));

  writeFileSync(join(outputDir, 'index.html'), renderIndex(pages), 'utf8');
  return pages;
}
