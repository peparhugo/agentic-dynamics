import { promises as fs } from 'node:fs';
import path from 'node:path';
import matter from 'gray-matter';
import { marked } from 'marked';

export interface Frontmatter {
  title?: string;
  date?: string | Date;
  tags?: string[] | string;
}

export interface Page {
  title: string;
  date?: string;
  tags: string[];
  url: string;
  html: string;
}

export interface BuildOptions {
  content?: string;
  output?: string;
}

function escapeHtml(value: string): string {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

async function markdownFiles(directory: string): Promise<string[]> {
  const entries = await fs.readdir(directory, { withFileTypes: true });
  const files = await Promise.all(entries.map(async (entry) => {
    const fullPath = path.join(directory, entry.name);
    if (entry.isDirectory()) return markdownFiles(fullPath);
    return /\.md$/i.test(entry.name) ? [fullPath] : [];
  }));
  return files.flat().sort();
}

function normalizeDate(value: unknown): string | undefined {
  if (value instanceof Date) return value.toISOString().slice(0, 10);
  if (typeof value === 'string' && value.trim()) return value.trim();
  return undefined;
}

function normalizeTags(value: unknown): string[] {
  if (Array.isArray(value)) return value.map(String).map((tag) => tag.trim()).filter(Boolean);
  if (typeof value === 'string') return value.split(',').map((tag) => tag.trim()).filter(Boolean);
  return [];
}

function layout(title: string, body: string): string {
  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>${escapeHtml(title)}</title>
</head>
<body>
${body}
</body>
</html>
`;
}

function renderPage(page: Page): string {
  const metadata = [
    page.date ? `<time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : '',
    ...page.tags.map((tag) => `<span class="tag">${escapeHtml(tag)}</span>`),
  ].filter(Boolean).join(' ');
  return layout(page.title, `<main>
  <article>
    <header><h1>${escapeHtml(page.title)}</h1>${metadata ? `\n    <p>${metadata}</p>` : ''}</header>
    ${page.html}
  </article>
</main>`);
}

function renderIndex(pages: Page[]): string {
  const items = pages.map((page) => {
    const date = page.date ? ` <time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : '';
    return `    <li><a href="${escapeHtml(page.url)}">${escapeHtml(page.title)}</a>${date}</li>`;
  }).join('\n');
  return layout('Pages', `<main>
  <h1>Pages</h1>
  <ul>
${items}
  </ul>
</main>`);
}

export async function buildSite(options: BuildOptions = {}): Promise<Page[]> {
  const contentDirectory = path.resolve(options.content ?? './content');
  const outputDirectory = path.resolve(options.output ?? './dist');
  if (contentDirectory === outputDirectory) {
    throw new Error('Content and output directories must be different');
  }
  const files = await markdownFiles(contentDirectory);

  const pages = await Promise.all(files.map(async (file): Promise<Page> => {
    const source = await fs.readFile(file, 'utf8');
    const parsed = matter(source);
    const frontmatter = parsed.data as Frontmatter;
    const relativePath = path.relative(contentDirectory, file);
    const url = relativePath.replace(/\.md$/i, '.html').split(path.sep).join('/');
    const fallbackTitle = path.basename(file, path.extname(file));
    return {
      title: typeof frontmatter.title === 'string' && frontmatter.title.trim()
        ? frontmatter.title.trim()
        : fallbackTitle,
      date: normalizeDate(frontmatter.date),
      tags: normalizeTags(frontmatter.tags),
      url,
      html: await marked.parse(parsed.content),
    };
  }));

  pages.sort((left, right) => {
    if (left.date && right.date && left.date !== right.date) return right.date.localeCompare(left.date);
    if (left.date !== right.date) return left.date ? -1 : 1;
    return left.title.localeCompare(right.title);
  });

  await fs.rm(outputDirectory, { recursive: true, force: true });
  await fs.mkdir(outputDirectory, { recursive: true });
  await Promise.all(pages.map(async (page) => {
    const destination = path.join(outputDirectory, ...page.url.split('/'));
    await fs.mkdir(path.dirname(destination), { recursive: true });
    await fs.writeFile(destination, renderPage(page), 'utf8');
  }));
  await fs.writeFile(path.join(outputDirectory, 'index.html'), renderIndex(pages), 'utf8');
  return pages;
}
