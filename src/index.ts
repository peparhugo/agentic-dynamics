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
  html: string;
  outputPath: string;
  url: string;
}

export interface BuildOptions {
  contentDir?: string;
  outputDir?: string;
}

const escapeHtml = (value: string): string =>
  value.replace(/[&<>'"]/g, (character) => {
    const entities: Record<string, string> = {
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      "'": '&#39;',
      '"': '&quot;',
    };
    return entities[character];
  });

const normalizeDate = (value: unknown): string | undefined => {
  if (value instanceof Date && !Number.isNaN(value.valueOf())) {
    return value.toISOString().slice(0, 10);
  }
  if (typeof value === 'string' && value.trim()) {
    return value.trim();
  }
  return undefined;
};

const normalizeTags = (value: unknown): string[] => {
  if (Array.isArray(value)) {
    return value.filter((tag): tag is string => typeof tag === 'string').map((tag) => tag.trim()).filter(Boolean);
  }
  if (typeof value === 'string') {
    return value.split(',').map((tag) => tag.trim()).filter(Boolean);
  }
  return [];
};

const titleFromFilename = (filename: string): string => {
  const name = path.basename(filename, path.extname(filename));
  return name
    .split(/[-_]+/)
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
};

export function parseMarkdown(source: string, relativePath: string): Page {
  const parsed = matter(source);
  const data = parsed.data as Frontmatter;
  const title = typeof data.title === 'string' && data.title.trim()
    ? data.title.trim()
    : titleFromFilename(relativePath);
  const htmlPath = relativePath.replace(/\.md$/i, '.html');
  const outputPath = htmlPath === 'index.html' ? 'index-page.html' : htmlPath;

  return {
    title,
    date: normalizeDate(data.date),
    tags: normalizeTags(data.tags),
    html: marked.parse(parsed.content, { async: false }) as string,
    outputPath,
    url: outputPath.split(path.sep).join('/'),
  };
}

const renderLayout = (title: string, content: string): string => `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>${escapeHtml(title)}</title>
</head>
<body>
${content}
</body>
</html>
`;

export function renderPage(page: Page): string {
  const date = page.date ? `\n  <time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : '';
  const tags = page.tags.length
    ? `\n  <ul class="tags">${page.tags.map((tag) => `<li>${escapeHtml(tag)}</li>`).join('')}</ul>`
    : '';
  return renderLayout(page.title, `  <main>\n  <article>\n  <header>\n  <h1>${escapeHtml(page.title)}</h1>${date}${tags}\n  </header>\n${page.html}  </article>\n  </main>`);
}

export function renderIndex(pages: Page[]): string {
  const items = pages.map((page) => {
    const date = page.date ? ` <time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : '';
    return `    <li><a href="${escapeHtml(page.url)}">${escapeHtml(page.title)}</a>${date}</li>`;
  }).join('\n');
  const list = items ? `\n  <ul>\n${items}\n  </ul>` : '\n  <p>No pages found.</p>';
  return renderLayout('Pages', `  <main>\n  <h1>Pages</h1>${list}\n  </main>`);
}

async function markdownFiles(directory: string, base = directory): Promise<string[]> {
  const entries = await fs.readdir(directory, { withFileTypes: true });
  const files = await Promise.all(entries.map(async (entry): Promise<string[]> => {
    const fullPath = path.join(directory, entry.name);
    if (entry.isDirectory()) return markdownFiles(fullPath, base);
    return entry.isFile() && /\.md$/i.test(entry.name) ? [path.relative(base, fullPath)] : [];
  }));
  return files.flat().sort((left, right) => left.localeCompare(right));
}

export async function buildSite(options: BuildOptions = {}): Promise<Page[]> {
  const contentDir = path.resolve(options.contentDir ?? './content');
  const outputDir = path.resolve(options.outputDir ?? './dist');
  const outputRelativeToContent = path.relative(contentDir, outputDir);
  const contentRelativeToOutput = path.relative(outputDir, contentDir);
  const isWithin = (relativePath: string): boolean =>
    relativePath === '' || (!relativePath.startsWith('..') && !path.isAbsolute(relativePath));
  if (isWithin(outputRelativeToContent) || isWithin(contentRelativeToOutput)) {
    throw new Error('Content and output directories must not overlap');
  }

  const stats = await fs.stat(contentDir).catch(() => undefined);
  if (!stats?.isDirectory()) {
    throw new Error(`Content directory does not exist: ${contentDir}`);
  }

  const files = await markdownFiles(contentDir);
  const pages = await Promise.all(files.map(async (relativePath) => {
    const source = await fs.readFile(path.join(contentDir, relativePath), 'utf8');
    return parseMarkdown(source, relativePath);
  }));

  pages.sort((left, right) => {
    if (left.date && right.date && left.date !== right.date) return right.date.localeCompare(left.date);
    if (left.date !== right.date) return left.date ? -1 : 1;
    return left.title.localeCompare(right.title);
  });

  await fs.rm(outputDir, { recursive: true, force: true });
  await fs.mkdir(outputDir, { recursive: true });
  await Promise.all(pages.map(async (page) => {
    const destination = path.join(outputDir, page.outputPath);
    await fs.mkdir(path.dirname(destination), { recursive: true });
    await fs.writeFile(destination, renderPage(page), 'utf8');
  }));
  await fs.writeFile(path.join(outputDir, 'index.html'), renderIndex(pages), 'utf8');
  return pages;
}
