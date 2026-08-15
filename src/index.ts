import { promises as fs } from 'node:fs';
import path from 'node:path';
import matter from 'gray-matter';
import { marked } from 'marked';

export interface Frontmatter {
  title?: string;
  date?: string;
  tags?: string[];
  [key: string]: unknown;
}

export interface ParsedMarkdown {
  data: Frontmatter;
  content: string;
  html: string;
}

export interface GeneratedPage extends ParsedMarkdown {
  sourcePath: string;
  outputPath: string;
  url: string;
  title: string;
}

export interface BuildOptions {
  contentDir?: string;
  outputDir?: string;
}

function parseScalar(value: string): unknown {
  const trimmed = value.trim();
  if (!trimmed) return '';

  if (trimmed.startsWith('[') && trimmed.endsWith(']')) {
    return trimmed
      .slice(1, -1)
      .split(',')
      .map((item) => String(parseScalar(item)))
      .filter(Boolean);
  }

  if ((trimmed.startsWith('"') && trimmed.endsWith('"')) ||
      (trimmed.startsWith("'") && trimmed.endsWith("'"))) {
    return trimmed.slice(1, -1);
  }
  if (trimmed === 'true') return true;
  if (trimmed === 'false') return false;
  if (trimmed === 'null') return null;
  if (/^-?\d+(\.\d+)?$/.test(trimmed)) return Number(trimmed);
  return trimmed;
}

function parseYamlFrontmatter(source: string): { data: Frontmatter; content: string } {
  const normalized = source.replace(/^\uFEFF/, '');
  const match = normalized.match(/^---[ \t]*\r?\n([\s\S]*?)\r?\n---[ \t]*(?:\r?\n|$)/);
  if (!match) return { data: {}, content: source };

  const data: Frontmatter = {};
  let listKey: string | undefined;

  for (const rawLine of match[1].split(/\r?\n/)) {
    const listItem = rawLine.match(/^\s+-\s+(.+)$/);
    if (listItem && listKey) {
      const current = data[listKey];
      data[listKey] = [...(Array.isArray(current) ? current : []), String(parseScalar(listItem[1]))];
      continue;
    }

    const entry = rawLine.match(/^\s*([^#:][^:]*):\s*(.*?)\s*$/);
    if (!entry) continue;
    const key = entry[1].trim();
    data[key] = entry[2] === '' ? [] : parseScalar(entry[2]);
    listKey = entry[2] === '' ? key : undefined;
  }

  return { data, content: normalized.slice(match[0].length) };
}

function normalizeFrontmatter(data: Record<string, unknown>): Frontmatter {
  const normalized: Frontmatter = { ...data };
  if (data.title != null) normalized.title = String(data.title);
  if (data.date instanceof Date) normalized.date = data.date.toISOString();
  else if (data.date != null) normalized.date = String(data.date);
  if (typeof data.tags === 'string') {
    normalized.tags = data.tags.split(',').map((tag) => tag.trim()).filter(Boolean);
  } else if (Array.isArray(data.tags)) {
    normalized.tags = data.tags.map(String);
  }
  return normalized;
}

export function parseMarkdown(source: string): ParsedMarkdown {
  const yaml = parseYamlFrontmatter(source);
  // gray-matter still handles JSON frontmatter and exposes a consistent result shape.
  const parsed = matter(yaml.content);
  const data = normalizeFrontmatter({ ...parsed.data, ...yaml.data });
  return { data, content: parsed.content, html: marked.parse(parsed.content) as string };
}

function escapeHtml(value: string): string {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function document(title: string, body: string): string {
  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>${escapeHtml(title)}</title>
</head>
<body>
${body}
</body>
</html>
`;
}

export function renderPage(page: Pick<GeneratedPage, 'title' | 'data' | 'html'>): string {
  const date = page.data.date ? `<time datetime="${escapeHtml(page.data.date)}">${escapeHtml(page.data.date)}</time>` : '';
  const tags = page.data.tags?.length
    ? `<ul class="tags">${page.data.tags.map((tag) => `<li>${escapeHtml(tag)}</li>`).join('')}</ul>`
    : '';
  return document(page.title, `<main>
  <article>
    <header><h1>${escapeHtml(page.title)}</h1>${date}${tags}</header>
    ${page.html}
  </article>
</main>`);
}

export function renderIndex(pages: GeneratedPage[]): string {
  const items = pages.map((page) => {
    const date = page.data.date ? ` <time datetime="${escapeHtml(page.data.date)}">${escapeHtml(page.data.date)}</time>` : '';
    return `<li><a href="${escapeHtml(page.url)}">${escapeHtml(page.title)}</a>${date}</li>`;
  }).join('\n    ');
  return document('Pages', `<main>
  <h1>Pages</h1>
  <ul>
    ${items}
  </ul>
</main>`);
}

async function markdownFiles(directory: string): Promise<string[]> {
  const entries = await fs.readdir(directory, { withFileTypes: true });
  const files = await Promise.all(entries.map(async (entry) => {
    const entryPath = path.join(directory, entry.name);
    if (entry.isDirectory()) return markdownFiles(entryPath);
    return entry.isFile() && /\.md$/i.test(entry.name) ? [entryPath] : [];
  }));
  return files.flat().sort();
}

export async function buildSite(options: BuildOptions = {}): Promise<GeneratedPage[]> {
  const contentDir = path.resolve(options.contentDir ?? './content');
  const outputDir = path.resolve(options.outputDir ?? './dist');
  const files = await markdownFiles(contentDir);

  const pages = await Promise.all(files.map(async (sourcePath): Promise<GeneratedPage> => {
    const source = await fs.readFile(sourcePath, 'utf8');
    const parsed = parseMarkdown(source);
    const relative = path.relative(contentDir, sourcePath).replace(/\.md$/i, '.html');
    const title = parsed.data.title || path.basename(sourcePath, path.extname(sourcePath));
    return {
      ...parsed,
      sourcePath,
      outputPath: path.join(outputDir, relative),
      url: relative.split(path.sep).map(encodeURIComponent).join('/'),
      title,
    };
  }));

  pages.sort((a, b) => {
    if (a.data.date && b.data.date) return b.data.date.localeCompare(a.data.date);
    return a.title.localeCompare(b.title);
  });

  await fs.rm(outputDir, { recursive: true, force: true });
  await fs.mkdir(outputDir, { recursive: true });
  await Promise.all(pages.map(async (page) => {
    await fs.mkdir(path.dirname(page.outputPath), { recursive: true });
    await fs.writeFile(page.outputPath, renderPage(page), 'utf8');
  }));
  await fs.writeFile(path.join(outputDir, 'index.html'), renderIndex(pages), 'utf8');
  return pages;
}
