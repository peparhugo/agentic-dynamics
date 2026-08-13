import { existsSync } from 'node:fs';
import { mkdir, readdir, readFile, rm, writeFile } from 'node:fs/promises';
import { basename, dirname, extname, join, relative } from 'node:path';
import matter from 'gray-matter';
import { marked } from 'marked';

export interface Page {
  title: string;
  date?: string;
  tags: string[];
  slug: string;
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
  const files = await Promise.all(entries.map(async (entry) => {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) return markdownFiles(path);
    return ['.md', '.markdown'].includes(extname(entry.name).toLowerCase()) ? [path] : [];
  }));
  return files.flat();
}

function layout(title: string, content: string): string {
  return `<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>${escapeHtml(title)}</title></head>
<body><main>${content}</main></body>
</html>
`;
}

export async function buildSite(options: BuildOptions = {}): Promise<Page[]> {
  const contentDir = options.contentDir ?? './content';
  const outputDir = options.outputDir ?? './dist';
  if (!existsSync(contentDir)) throw new Error(`Content directory does not exist: ${contentDir}`);

  const files = await markdownFiles(contentDir);
  const pages = await Promise.all(files.map(async (file): Promise<Page> => {
    const source = await readFile(file, 'utf8');
    const parsed = matter(source);
    const relativePath = relative(contentDir, file).replace(/\\/g, '/');
    const slug = relativePath.replace(/\.(md|markdown)$/i, '.html');
    const fallbackTitle = basename(file, extname(file));
    const title = typeof parsed.data.title === 'string' ? parsed.data.title : fallbackTitle;
    const dateValue = parsed.data.date;
    const date = dateValue === undefined
      ? undefined
      : dateValue instanceof Date
        ? dateValue.toISOString().slice(0, 10)
        : String(dateValue);
    const tags = Array.isArray(parsed.data.tags) ? parsed.data.tags.map(String) : [];
    return { title, date, tags, slug, html: await marked.parse(parsed.content) };
  }));

  pages.sort((left, right) => left.title.localeCompare(right.title));
  await rm(outputDir, { recursive: true, force: true });
  await mkdir(outputDir, { recursive: true });

  await Promise.all(pages.map(async (page) => {
    const destination = join(outputDir, page.slug);
    await mkdir(dirname(destination), { recursive: true });
    await writeFile(destination, layout(page.title, page.html), 'utf8');
  }));

  const links = pages.map((page) => `<li><a href="${encodeURI(page.slug)}">${escapeHtml(page.title)}</a></li>`).join('\n');
  await writeFile(join(outputDir, 'index.html'), layout('Index', `<h1>Pages</h1><ul>${links}</ul>`), 'utf8');
  return pages;
}
