import { promises as fs } from 'node:fs';
import path from 'node:path';
import matter from 'gray-matter';
import { marked } from 'marked';

export interface BuildOptions {
  contentDir?: string;
  outputDir?: string;
}

export interface GeneratedPage {
  title: string;
  date?: string;
  tags: string[];
  outputPath: string;
  url: string;
}

interface Page extends GeneratedPage {
  html: string;
}

function escapeHtml(value: string): string {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function renderDocument(title: string, body: string): string {
  const safeTitle = escapeHtml(title);
  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>${safeTitle}</title>
</head>
<body>
  <main>
    <h1>${safeTitle}</h1>
${body}
  </main>
</body>
</html>
`;
}

async function markdownFiles(directory: string): Promise<string[]> {
  const entries = await fs.readdir(directory, { withFileTypes: true });
  const files = await Promise.all(
    entries.map(async (entry): Promise<string[]> => {
      const entryPath = path.join(directory, entry.name);
      if (entry.isDirectory()) return markdownFiles(entryPath);
      return entry.isFile() && /\.md$/i.test(entry.name) ? [entryPath] : [];
    }),
  );
  return files.flat().sort();
}

function normalizeDate(value: unknown): string | undefined {
  if (value instanceof Date && !Number.isNaN(value.valueOf())) {
    return value.toISOString().slice(0, 10);
  }
  if (typeof value === 'string' || typeof value === 'number') return String(value);
  return undefined;
}

function normalizeTags(value: unknown): string[] {
  if (Array.isArray(value)) return value.map(String);
  if (typeof value === 'string') return value.split(',').map((tag) => tag.trim()).filter(Boolean);
  return [];
}

function indexBody(pages: Page[]): string {
  const items = pages.map((page) => {
    const date = page.date ? ` <time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : '';
    const tags = page.tags.length > 0 ? ` <span>${page.tags.map(escapeHtml).join(', ')}</span>` : '';
    return `      <li><a href="${escapeHtml(page.url)}">${escapeHtml(page.title)}</a>${date}${tags}</li>`;
  });
  return `    <ul>\n${items.join('\n')}\n    </ul>`;
}

function isWithin(parent: string, candidate: string): boolean {
  const relative = path.relative(parent, candidate);
  return relative === '' || (!relative.startsWith(`..${path.sep}`) && relative !== '..' && !path.isAbsolute(relative));
}

/** Build all Markdown documents and return metadata for the generated pages. */
export async function buildSite(options: BuildOptions = {}): Promise<GeneratedPage[]> {
  const contentDir = path.resolve(options.contentDir ?? './content');
  const outputDir = path.resolve(options.outputDir ?? './dist');
  if (isWithin(contentDir, outputDir) || isWithin(outputDir, contentDir)) {
    throw new Error('Content and output directories must not overlap');
  }
  const files = await markdownFiles(contentDir);

  const pages = await Promise.all(files.map(async (file): Promise<Page> => {
    const source = await fs.readFile(file, 'utf8');
    const parsed = matter(source);
    const relativePath = path.relative(contentDir, file).replace(/\.md$/i, '.html');
    const url = relativePath.split(path.sep).map(encodeURIComponent).join('/');
    const fallbackTitle = path.basename(file, path.extname(file));
    const title = typeof parsed.data.title === 'string' && parsed.data.title.trim()
      ? parsed.data.title.trim()
      : fallbackTitle;
    const markdownHtml = await marked.parse(parsed.content);
    const date = normalizeDate(parsed.data.date);
    const tags = normalizeTags(parsed.data.tags);
    const metadata = [
      date ? `    <time datetime="${escapeHtml(date)}">${escapeHtml(date)}</time>` : '',
      tags.length > 0 ? `    <p>Tags: ${tags.map(escapeHtml).join(', ')}</p>` : '',
    ].filter(Boolean).join('\n');
    const body = `${metadata}${metadata ? '\n' : ''}    <article>\n${markdownHtml.trimEnd()}\n    </article>`;

    return {
      title,
      date,
      tags,
      outputPath: path.join(outputDir, relativePath),
      url,
      html: renderDocument(title, body),
    };
  }));

  const outputPaths = new Set<string>();
  for (const page of pages) {
    const normalizedPath = page.outputPath.toLowerCase();
    if (path.basename(normalizedPath) === 'index.html' && path.dirname(page.outputPath) === outputDir) {
      throw new Error('A root index.md conflicts with the generated index.html');
    }
    if (outputPaths.has(normalizedPath)) {
      throw new Error(`Multiple Markdown files produce the same output: ${page.outputPath}`);
    }
    outputPaths.add(normalizedPath);
  }

  await fs.rm(outputDir, { recursive: true, force: true });
  await Promise.all(pages.map(async (page) => {
    await fs.mkdir(path.dirname(page.outputPath), { recursive: true });
    await fs.writeFile(page.outputPath, page.html, 'utf8');
  }));
  await fs.mkdir(outputDir, { recursive: true });
  await fs.writeFile(path.join(outputDir, 'index.html'), renderDocument('Pages', indexBody(pages)), 'utf8');

  return pages.map(({ html: _html, ...page }) => page);
}
