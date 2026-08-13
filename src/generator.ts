import { mkdir, readdir, readFile, rm, writeFile } from 'node:fs/promises';
import { relative, resolve, sep } from 'node:path';
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

function escapeHtml(value: string): string {
  return value.replace(/[&<>"']/g, (character) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;'
  })[character]!);
}

async function markdownFiles(directory: string): Promise<string[]> {
  const entries = await readdir(directory, { withFileTypes: true });
  const paths = await Promise.all(entries.map(async (entry) => {
    const path = resolve(directory, entry.name);
    if (entry.isDirectory()) return markdownFiles(path);
    return entry.isFile() && /\.md$/i.test(entry.name) ? [path] : [];
  }));
  return paths.flat();
}

function outputPathFor(sourcePath: string, contentDir: string): string {
  const relativePath = relative(contentDir, sourcePath);
  return relativePath.replace(/\.md$/i, '.html');
}

function dateValue(value: unknown): string | undefined {
  if (value === undefined || value === null) return undefined;
  if (value instanceof Date) return value.toISOString().slice(0, 10);
  return String(value);
}

function pageDocument(page: Page): string {
  const metadata = [
    page.date ? `<time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : '',
    page.tags.length ? `<p>Tags: ${page.tags.map(escapeHtml).join(', ')}</p>` : ''
  ].filter(Boolean).join('\n');

  return `<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>${escapeHtml(page.title)}</title></head>
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

function indexDocument(pages: Page[]): string {
  const items = pages.map((page) => {
    const details = [page.date, page.tags.length ? page.tags.join(', ') : ''].filter(Boolean).join(' | ');
    const detailHtml = details ? ` <small>${escapeHtml(details)}</small>` : '';
    return `<li><a href="${encodeURI(page.outputPath.split(sep).join('/'))}">${escapeHtml(page.title)}</a>${detailHtml}</li>`;
  }).join('\n');
  return `<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Pages</title></head>
<body><main><h1>Pages</h1><ul>${items}</ul></main></body>
</html>
`;
}

export async function buildSite(options: BuildOptions = {}): Promise<Page[]> {
  const contentDir = resolve(options.contentDir ?? 'content');
  const outputDir = resolve(options.outputDir ?? 'dist');
  const files = await markdownFiles(contentDir);
  const pages = await Promise.all(files.map(async (sourcePath) => {
    const parsed = matter(await readFile(sourcePath, 'utf8'));
    const relativeOutput = outputPathFor(sourcePath, contentDir);
    const title = typeof parsed.data.title === 'string' && parsed.data.title.trim()
      ? parsed.data.title
      : relativeOutput.replace(/\.html$/i, '');
    const tags = Array.isArray(parsed.data.tags) ? parsed.data.tags.map(String) : [];
    return {
      sourcePath,
      outputPath: relativeOutput,
      title,
      date: dateValue(parsed.data.date),
      tags,
      html: await marked.parse(parsed.content)
    };
  }));

  pages.sort((a, b) => a.title.localeCompare(b.title));
  await rm(outputDir, { recursive: true, force: true });
  await mkdir(outputDir, { recursive: true });
  await Promise.all(pages.map(async (page) => {
    const destination = resolve(outputDir, page.outputPath);
    await mkdir(resolve(destination, '..'), { recursive: true });
    await writeFile(destination, pageDocument(page));
  }));
  await writeFile(resolve(outputDir, 'index.html'), indexDocument(pages));
  return pages;
}
