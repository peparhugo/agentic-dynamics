import { mkdir, readdir, readFile, rm, writeFile } from 'node:fs/promises';
import { basename, extname, join, relative, resolve, sep } from 'node:path';
import matter from 'gray-matter';
import { marked } from 'marked';

export interface Page {
  title: string;
  date?: string;
  tags: string[];
  outputPath: string;
  html: string;
}

export interface BuildOptions {
  contentDir?: string;
  outputDir?: string;
}

const escapeHtml = (value: string): string => value
  .replace(/&/g, '&amp;')
  .replace(/</g, '&lt;')
  .replace(/>/g, '&gt;')
  .replace(/"/g, '&quot;')
  .replace(/'/g, '&#39;');

async function markdownFiles(directory: string): Promise<string[]> {
  const entries = await readdir(directory, { withFileTypes: true });
  const paths = await Promise.all(entries.map(async (entry) => {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) {
      return markdownFiles(path);
    }
    return entry.isFile() && ['.md', '.markdown'].includes(extname(entry.name).toLowerCase()) ? [path] : [];
  }));
  return paths.flat();
}

function asString(value: unknown): string | undefined {
  return typeof value === 'string' && value.trim() ? value.trim() : undefined;
}

function asTags(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value.filter((tag): tag is string => typeof tag === 'string').map((tag) => tag.trim()).filter(Boolean);
  }
  return typeof value === 'string' ? value.split(',').map((tag) => tag.trim()).filter(Boolean) : [];
}

function document(title: string, body: string): string {
  return `<!doctype html>\n<html lang="en">\n<head>\n  <meta charset="utf-8">\n  <meta name="viewport" content="width=device-width, initial-scale=1">\n  <title>${escapeHtml(title)}</title>\n</head>\n<body>\n  <main>\n${body}\n  </main>\n</body>\n</html>\n`;
}

export async function buildSite(options: BuildOptions = {}): Promise<Page[]> {
  const contentDir = resolve(options.contentDir ?? 'content');
  const outputDir = resolve(options.outputDir ?? 'dist');
  const files = await markdownFiles(contentDir);
  const pages = await Promise.all(files.map(async (file): Promise<Page> => {
    const parsed = matter(await readFile(file, 'utf8'));
    const sourcePath = relative(contentDir, file);
    const outputPath = sourcePath.replace(/\.(md|markdown)$/i, '.html').split(sep).join('/');
    const title = asString(parsed.data.title) ?? basename(file, extname(file));
    const date = asString(parsed.data.date);
    const tags = asTags(parsed.data.tags);
    return { title, date, tags, outputPath, html: await marked.parse(parsed.content) };
  }));

  pages.sort((a, b) => a.title.localeCompare(b.title));
  await rm(outputDir, { recursive: true, force: true });
  await mkdir(outputDir, { recursive: true });

  await Promise.all(pages.map(async (page) => {
    const destination = join(outputDir, page.outputPath);
    await mkdir(resolve(destination, '..'), { recursive: true });
    const metadata = [page.date, page.tags.length ? `Tags: ${page.tags.map(escapeHtml).join(', ')}` : ''].filter(Boolean).join(' | ');
    await writeFile(destination, document(page.title, `    <article>\n      <h1>${escapeHtml(page.title)}</h1>${metadata ? `\n      <p>${metadata}</p>` : ''}\n      ${page.html.trim()}\n    </article>`));
  }));

  const links = pages.map((page) => `      <li><a href="${encodeURI(page.outputPath)}">${escapeHtml(page.title)}</a></li>`).join('\n');
  await writeFile(join(outputDir, 'index.html'), document('Index', `    <h1>Pages</h1>\n    <ul>\n${links}\n    </ul>`));
  return pages;
}
