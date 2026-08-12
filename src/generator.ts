import { promises as fs } from 'node:fs';
import path from 'node:path';
import matter from 'gray-matter';
import { marked } from 'marked';

export interface BuildOptions {
  contentDir?: string;
  outputDir?: string;
}

export interface Page {
  title: string;
  date?: string;
  tags: string[];
  html: string;
  sourcePath: string;
  outputPath: string;
}

interface Frontmatter {
  title?: unknown;
  date?: unknown;
  tags?: unknown;
}

const escapeHtml = (value: string): string => value
  .replaceAll('&', '&amp;')
  .replaceAll('<', '&lt;')
  .replaceAll('>', '&gt;')
  .replaceAll('"', '&quot;')
  .replaceAll("'", '&#39;');

const normalizeTags = (value: unknown): string[] => {
  if (Array.isArray(value)) return value.map(String).filter(Boolean);
  if (typeof value === 'string') return value.split(',').map((tag) => tag.trim()).filter(Boolean);
  return [];
};

const normalizeDate = (value: unknown): string | undefined => {
  if (value instanceof Date) return value.toISOString().slice(0, 10);
  if (typeof value === 'string' || typeof value === 'number') return String(value);
  return undefined;
};

async function markdownFiles(directory: string): Promise<string[]> {
  const entries = await fs.readdir(directory, { withFileTypes: true });
  const files: string[] = [];
  for (const entry of entries) {
    const entryPath = path.join(directory, entry.name);
    if (entry.isDirectory()) files.push(...await markdownFiles(entryPath));
    else if (entry.isFile() && /\.(md|markdown)$/i.test(entry.name)) files.push(entryPath);
  }
  return files.sort();
}

const outputName = (relativePath: string): string =>
  relativePath.replace(/\.(md|markdown)$/i, '.html');

const pageDocument = (page: Page): string => {
  const date = page.date ? `<time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : '';
  const tags = page.tags.length > 0
    ? `<ul class="tags">${page.tags.map((tag) => `<li>${escapeHtml(tag)}</li>`).join('')}</ul>`
    : '';
  return `<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>${escapeHtml(page.title)}</title></head>
<body><main><h1>${escapeHtml(page.title)}</h1>${date}${tags}<article>${page.html}</article></main></body>
</html>
`;
};

const indexDocument = (pages: Page[]): string => `<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Index</title></head>
<body><main><h1>Pages</h1><ul>${pages.map((page) => `<li><a href="${encodeURI(page.outputPath)}">${escapeHtml(page.title)}</a>${page.date ? ` <time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : ''}</li>`).join('')}</ul></main></body>
</html>
`;

export async function buildSite(options: BuildOptions = {}): Promise<Page[]> {
  const contentDir = path.resolve(options.contentDir ?? './content');
  const outputDir = path.resolve(options.outputDir ?? './dist');
  const files = await markdownFiles(contentDir);
  const pages: Page[] = [];

  for (const sourcePath of files) {
    const parsed = matter(await fs.readFile(sourcePath, 'utf8'));
    const metadata = parsed.data as Frontmatter;
    const relativePath = path.relative(contentDir, sourcePath).split(path.sep).join('/');
    const outputPath = outputName(relativePath);
    pages.push({
      title: typeof metadata.title === 'string' && metadata.title.trim() ? metadata.title : path.basename(relativePath, path.extname(relativePath)),
      date: normalizeDate(metadata.date),
      tags: normalizeTags(metadata.tags),
      html: marked.parse(parsed.content),
      sourcePath,
      outputPath,
    });
  }

  pages.sort((a, b) => (b.date ?? '').localeCompare(a.date ?? '') || a.outputPath.localeCompare(b.outputPath));
  await fs.rm(outputDir, { recursive: true, force: true });
  await fs.mkdir(outputDir, { recursive: true });
  await fs.writeFile(path.join(outputDir, 'index.html'), indexDocument(pages));
  for (const page of pages) {
    const destination = path.join(outputDir, page.outputPath);
    await fs.mkdir(path.dirname(destination), { recursive: true });
    await fs.writeFile(destination, pageDocument(page));
  }
  return pages;
}
