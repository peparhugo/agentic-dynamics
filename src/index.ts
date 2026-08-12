import matter from 'gray-matter';
import { marked } from 'marked';
import { promises as fs } from 'node:fs';
import path from 'node:path';

export interface Page {
  title: string;
  date?: string;
  tags: string[];
  slug: string;
  html: string;
  sourcePath: string;
}

export interface BuildOptions {
  contentDir?: string;
  outputDir?: string;
}

function escapeHtml(value: string): string {
  return value.replace(/[&<>"']/g, (character) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[character] as string);
}

function normaliseTags(value: unknown): string[] {
  if (Array.isArray(value)) return value.map(String);
  if (typeof value === 'string') return value.split(',').map((tag) => tag.trim()).filter(Boolean);
  return [];
}

function normaliseDate(value: unknown): string | undefined {
  if (value === undefined || value === null) return undefined;
  if (value instanceof Date) return value.toISOString().slice(0, 10);
  return String(value);
}

export async function parseMarkdown(source: string, sourcePath = 'page.md'): Promise<Page> {
  const parsed = matter(source);
  const name = path.basename(sourcePath, path.extname(sourcePath));
  const title = typeof parsed.data.title === 'string' && parsed.data.title.trim()
    ? parsed.data.title.trim()
    : name.replace(/[-_]+/g, ' ');
  const date = normaliseDate(parsed.data.date);

  return {
    title,
    date,
    tags: normaliseTags(parsed.data.tags),
    slug: `${name}.html`,
    html: await marked.parse(parsed.content),
    sourcePath
  };
}

async function markdownFiles(directory: string): Promise<string[]> {
  const entries = await fs.readdir(directory, { withFileTypes: true });
  const files: string[] = [];
  for (const entry of entries) {
    const fullPath = path.join(directory, entry.name);
    if (entry.isDirectory()) files.push(...await markdownFiles(fullPath));
    else if (/\.md$/i.test(entry.name)) files.push(fullPath);
  }
  return files.sort();
}

function document(title: string, body: string): string {
  return `<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n<title>${escapeHtml(title)}</title>\n</head>\n<body>\n${body}\n</body>\n</html>\n`;
}

export async function buildSite(options: BuildOptions = {}): Promise<Page[]> {
  const contentDir = path.resolve(options.contentDir ?? './content');
  const outputDir = path.resolve(options.outputDir ?? './dist');
  const files = await markdownFiles(contentDir);
  const pages = await Promise.all(files.map(async (file) => {
    const relative = path.relative(contentDir, file);
    const page = await parseMarkdown(await fs.readFile(file, 'utf8'), relative);
    page.slug = `${relative.replace(/\.md$/i, '')}.html`;
    page.sourcePath = relative;
    return page;
  }));

  await fs.rm(outputDir, { recursive: true, force: true });
  await fs.mkdir(outputDir, { recursive: true });
  await Promise.all(pages.map(async (page) => {
    const outputPath = path.join(outputDir, page.slug);
    await fs.mkdir(path.dirname(outputPath), { recursive: true });
    const metadata = [page.date ? `<p class="date">${escapeHtml(page.date)}</p>` : '', page.tags.length ? `<p class="tags">${page.tags.map(escapeHtml).join(', ')}</p>` : ''].join('');
    await fs.writeFile(outputPath, document(page.title, `<main><h1>${escapeHtml(page.title)}</h1>${metadata}${page.html}</main>`));
  }));

  const links = pages.map((page) => `<li><a href="${escapeHtml(page.slug)}">${escapeHtml(page.title)}</a>${page.date ? ` <time>${escapeHtml(page.date)}</time>` : ''}</li>`).join('\n');
  await fs.writeFile(path.join(outputDir, 'index.html'), document('Home', `<main><h1>Pages</h1><ul>${links}</ul></main>`));
  return pages;
}
