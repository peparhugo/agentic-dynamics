import { promises as fs } from 'node:fs';
import path from 'node:path';
import matter from 'gray-matter';
import { marked } from 'marked';
import { BuildOptions, Frontmatter, Page } from './types';

const DEFAULT_CONTENT_DIR = './content';
const DEFAULT_OUTPUT_DIR = './dist';

function asString(value: unknown): string | undefined {
  if (value instanceof Date) return value.toISOString().slice(0, 10);
  if (typeof value === 'string' || typeof value === 'number') return String(value);
  return undefined;
}

function normalizeTags(value: unknown): string[] {
  if (Array.isArray(value)) return value.map(String);
  if (typeof value === 'string') return value.split(',').map((tag) => tag.trim()).filter(Boolean);
  return [];
}

function normalizeFrontmatter(data: Record<string, unknown>, fallbackTitle: string): Frontmatter {
  return {
    title: asString(data.title) || fallbackTitle,
    date: asString(data.date),
    tags: normalizeTags(data.tags),
  };
}

function titleFromFilename(filePath: string): string {
  return path.basename(filePath, path.extname(filePath)).replace(/[-_]+/g, ' ')
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

async function markdownFiles(directory: string): Promise<string[]> {
  const entries = await fs.readdir(directory, { withFileTypes: true });
  const files: string[] = [];
  for (const entry of entries) {
    const entryPath = path.join(directory, entry.name);
    if (entry.isDirectory()) files.push(...await markdownFiles(entryPath));
    else if (entry.isFile() && /\.md$/i.test(entry.name)) files.push(entryPath);
  }
  return files.sort((a, b) => a.localeCompare(b));
}

export async function parseMarkdown(sourcePath: string, content: string, contentDir?: string): Promise<Page> {
  const parsed = matter(content);
  const relativePath = contentDir ? path.relative(contentDir, sourcePath) : path.basename(sourcePath);
  const slug = relativePath.replace(/\\/g, '/').replace(/\.md$/i, '');
  const frontmatter = normalizeFrontmatter(parsed.data as Record<string, unknown>, titleFromFilename(sourcePath));
  return {
    sourcePath,
    outputPath: `${slug}.html`,
    slug,
    frontmatter,
    html: await marked.parse(parsed.content),
  };
}

function escapeHtml(value: string): string {
  return value.replace(/[&<>"']/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[character] as string));
}

function pageDocument(page: Page): string {
  return `<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n<title>${escapeHtml(page.frontmatter.title)}</title>\n</head>\n<body>\n<main>\n<h1>${escapeHtml(page.frontmatter.title)}</h1>\n${page.frontmatter.date ? `<time datetime="${escapeHtml(page.frontmatter.date)}">${escapeHtml(page.frontmatter.date)}</time>\n` : ''}${page.html}</main>\n</body>\n</html>\n`;
}

function indexDocument(pages: Page[]): string {
  const items = pages.map((page) => {
    const metadata = [page.frontmatter.date, ...page.frontmatter.tags].filter(Boolean).map(escapeHtml).join(' | ');
    return `<li><a href="${encodeURI(page.outputPath)}">${escapeHtml(page.frontmatter.title)}</a>${metadata ? ` <small>${metadata}</small>` : ''}</li>`;
  }).join('\n');
  return `<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n<title>Home</title>\n</head>\n<body>\n<main>\n<h1>Pages</h1>\n<ul>\n${items}\n</ul>\n</main>\n</body>\n</html>\n`;
}

export async function buildSite(options: BuildOptions = {}): Promise<Page[]> {
  const contentDir = path.resolve(options.contentDir || DEFAULT_CONTENT_DIR);
  const outputDir = path.resolve(options.outputDir || DEFAULT_OUTPUT_DIR);
  const files = await markdownFiles(contentDir);
  const pages = await Promise.all(files.map(async (file) => parseMarkdown(file, await fs.readFile(file, 'utf8'), contentDir)));
  pages.sort((a, b) => a.slug.localeCompare(b.slug));
  await fs.mkdir(outputDir, { recursive: true });
  await Promise.all(pages.map(async (page) => {
    const destination = path.join(outputDir, page.outputPath);
    await fs.mkdir(path.dirname(destination), { recursive: true });
    await fs.writeFile(destination, pageDocument(page), 'utf8');
  }));
  await fs.writeFile(path.join(outputDir, 'index.html'), indexDocument(pages), 'utf8');
  return pages;
}

export { escapeHtml, indexDocument, pageDocument };
