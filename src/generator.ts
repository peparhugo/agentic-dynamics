import { promises as fs } from 'node:fs';
import path from 'node:path';
import matter from 'gray-matter';
import { marked } from 'marked';

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

function asString(value: unknown): string | undefined {
  return typeof value === 'string' ? value : undefined;
}

function asDateString(value: unknown): string | undefined {
  if (typeof value === 'string') return value;
  if (value instanceof Date && !Number.isNaN(value.valueOf())) return value.toISOString().slice(0, 10);
  return undefined;
}

function asTags(value: unknown): string[] {
  if (Array.isArray(value)) return value.filter((tag): tag is string => typeof tag === 'string');
  if (typeof value === 'string') return value.split(',').map((tag) => tag.trim()).filter(Boolean);
  return [];
}

function escapeHtml(value: string): string {
  return value.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function document(title: string, body: string): string {
  return `<!doctype html>\n<html lang="en">\n<head>\n  <meta charset="utf-8">\n  <meta name="viewport" content="width=device-width, initial-scale=1">\n  <title>${escapeHtml(title)}</title>\n</head>\n<body>\n${body}\n</body>\n</html>\n`;
}

async function markdownFiles(directory: string, relative = ''): Promise<string[]> {
  const entries = await fs.readdir(path.join(directory, relative), { withFileTypes: true });
  const files: string[] = [];
  for (const entry of entries) {
    const entryRelative = path.join(relative, entry.name);
    if (entry.isDirectory()) files.push(...await markdownFiles(directory, entryRelative));
    else if (entry.isFile() && /\.md$/i.test(entry.name)) files.push(entryRelative);
  }
  return files;
}

export async function readPages(contentDir: string): Promise<Page[]> {
  const files = (await markdownFiles(contentDir)).sort();
  return Promise.all(files.map(async (relativePath) => {
    const source = await fs.readFile(path.join(contentDir, relativePath), 'utf8');
    const parsed = matter(source);
    const fallbackTitle = path.basename(relativePath, path.extname(relativePath));
    const title = asString(parsed.data.title) ?? fallbackTitle;
    const outputPath = `${relativePath.slice(0, -path.extname(relativePath).length)}.html`;
    return {
      sourcePath: relativePath,
      outputPath,
      title,
      date: asDateString(parsed.data.date),
      tags: asTags(parsed.data.tags),
      html: await marked.parse(parsed.content)
    };
  }));
}

export async function buildSite(options: BuildOptions = {}): Promise<Page[]> {
  const contentDir = path.resolve(options.contentDir ?? './content');
  const outputDir = path.resolve(options.outputDir ?? './dist');
  const pages = await readPages(contentDir);
  await fs.rm(outputDir, { recursive: true, force: true });
  await fs.mkdir(outputDir, { recursive: true });

  for (const page of pages) {
    const target = path.join(outputDir, page.outputPath);
    await fs.mkdir(path.dirname(target), { recursive: true });
    const metadata = [page.date ? `<time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : '', page.tags.length ? `<p>Tags: ${page.tags.map(escapeHtml).join(', ')}</p>` : ''].filter(Boolean).join('\n');
    await fs.writeFile(target, document(page.title, `<article>\n<h1>${escapeHtml(page.title)}</h1>\n${metadata}\n${page.html}\n</article>`));
  }

  const links = pages.map((page) => `<li><a href="${page.outputPath.replaceAll(path.sep, '/')}">${escapeHtml(page.title)}</a>${page.date ? ` <time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : ''}</li>`).join('\n');
  await fs.writeFile(path.join(outputDir, 'index.html'), document('Home', `<h1>Pages</h1>\n<ul>\n${links}\n</ul>`));
  return pages;
}
