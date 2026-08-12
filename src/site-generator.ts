import fs from 'fs/promises';
import path from 'path';
import matter from 'gray-matter';
import { marked } from 'marked';

export interface Frontmatter {
  title?: string;
  date?: string | Date;
  tags?: string[] | string;
  [key: string]: unknown;
}

export interface Page {
  sourcePath: string;
  outputPath: string;
  title: string;
  date?: string;
  tags: string[];
  html: string;
}

export interface BuildOptions {
  contentDir?: string;
  outputDir?: string;
}

export interface BuildResult {
  pages: Page[];
  indexPath: string;
}

function normalizeTags(value: Frontmatter['tags']): string[] {
  if (Array.isArray(value)) return value.map(String);
  if (typeof value === 'string') return value.split(',').map((tag) => tag.trim()).filter(Boolean);
  return [];
}

function formatDate(value: Frontmatter['date']): string | undefined {
  if (!value) return undefined;
  return value instanceof Date ? value.toISOString().slice(0, 10) : String(value);
}

export function parseMarkdown(source: string, sourcePath = ''): Page {
  const parsed = matter(source);
  const data = parsed.data as Frontmatter;
  const title = typeof data.title === 'string' && data.title.trim()
    ? data.title.trim()
    : path.basename(sourcePath, path.extname(sourcePath));

  return {
    sourcePath,
    outputPath: sourcePath.replace(/\.md$/i, '.html'),
    title,
    date: formatDate(data.date),
    tags: normalizeTags(data.tags),
    html: marked.parse(parsed.content),
  };
}

async function markdownFiles(directory: string): Promise<string[]> {
  const entries = await fs.readdir(directory, { withFileTypes: true });
  const files: string[] = [];
  for (const entry of entries) {
    const entryPath = path.join(directory, entry.name);
    if (entry.isDirectory()) files.push(...await markdownFiles(entryPath));
    else if (entry.isFile() && /\.md$/i.test(entry.name)) files.push(entryPath);
  }
  return files.sort();
}

function escapeHtml(value: string): string {
  return value.replace(/[&<>"']/g, (character) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[character] as string));
}

function document(title: string, body: string): string {
  return `<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n<title>${escapeHtml(title)}</title>\n</head>\n<body>\n${body}\n</body>\n</html>\n`;
}

function pageDocument(page: Page): string {
  const metadata = [page.date, ...page.tags].filter(Boolean).map(escapeHtml).join(' | ');
  return document(page.title, `<main>\n<h1>${escapeHtml(page.title)}</h1>\n${metadata ? `<p>${metadata}</p>\n` : ''}${page.html}</main>`);
}

function indexDocument(pages: Page[]): string {
  const links = pages.map((page) => {
    const metadata = [page.date, ...page.tags].filter(Boolean).map(escapeHtml).join(' | ');
    return `<li><a href="${encodeURI(page.outputPath)}">${escapeHtml(page.title)}</a>${metadata ? ` <small>${metadata}</small>` : ''}</li>`;
  }).join('\n');
  return document('Index', `<main>\n<h1>Pages</h1>\n<ul>\n${links}\n</ul>\n</main>`);
}

export async function buildSite(options: BuildOptions = {}): Promise<BuildResult> {
  const contentDir = path.resolve(options.contentDir ?? './content');
  const outputDir = path.resolve(options.outputDir ?? './dist');
  const sourceFiles = await markdownFiles(contentDir);
  const pages = await Promise.all(sourceFiles.map(async (sourcePath) => {
    const source = await fs.readFile(sourcePath, 'utf8');
    const relativePath = path.relative(contentDir, sourcePath);
    const page = parseMarkdown(source, relativePath);
    const destination = path.join(outputDir, page.outputPath);
    await fs.mkdir(path.dirname(destination), { recursive: true });
    await fs.writeFile(destination, pageDocument(page), 'utf8');
    return page;
  }));
  pages.sort((a, b) => a.outputPath.localeCompare(b.outputPath));
  await fs.mkdir(outputDir, { recursive: true });
  const indexPath = path.join(outputDir, 'index.html');
  await fs.writeFile(indexPath, indexDocument(pages), 'utf8');
  return { pages, indexPath };
}
