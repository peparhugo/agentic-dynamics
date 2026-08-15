import { mkdir, readdir, readFile, rm, writeFile } from 'node:fs/promises';
import { dirname, join, relative, resolve, sep } from 'node:path';
import matter from 'gray-matter';
import { marked } from 'marked';

export interface Page {
  sourcePath: string;
  outputPath: string;
  slug: string;
  title: string;
  date?: string;
  tags: string[];
  html: string;
}

export interface BuildOptions {
  contentDir?: string;
  outputDir?: string;
}

type Frontmatter = Record<string, string | string[]>;

function escapeHtml(value: string): string {
  return value.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function parseYamlValue(value: string): string | string[] {
  const trimmed = value.trim();
  if (trimmed.startsWith('[') && trimmed.endsWith(']')) {
    return trimmed.slice(1, -1).split(',').map((item) => item.trim().replace(/^['"]|['"]$/g, '')).filter(Boolean);
  }
  return trimmed.replace(/^['"]|['"]$/g, '');
}

/** Extract the simple YAML subset supported by this generator before gray-matter parses content. */
export function parseYamlFrontmatter(source: string): { data: Frontmatter; content: string } {
  const match = source.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n?/);
  if (!match) return { data: {}, content: source };

  const data: Frontmatter = {};
  for (const line of match[1].split(/\r?\n/)) {
    const separator = line.indexOf(':');
    if (separator > 0) {
      const key = line.slice(0, separator).trim();
      const value = line.slice(separator + 1);
      if (key) data[key] = parseYamlValue(value);
    }
  }
  return { data, content: source.slice(match[0].length) };
}

export function parsePage(source: string, sourcePath: string, contentDir: string, outputDir: string): Page {
  const yaml = parseYamlFrontmatter(source);
  const parsed = matter(yaml.content);
  const data = { ...parsed.data, ...yaml.data } as Frontmatter;
  const sourceRelative = relative(contentDir, sourcePath);
  const slug = sourceRelative.replace(/\.md$/i, '').split(sep).join('/');
  const outputPath = join(outputDir, `${sourceRelative.replace(/\.md$/i, '')}.html`);
  const title = typeof data.title === 'string' && data.title ? data.title : slug.split('/').at(-1) ?? 'Untitled';
  const tags = Array.isArray(data.tags) ? data.tags : typeof data.tags === 'string' ? data.tags.split(',').map((tag) => tag.trim()).filter(Boolean) : [];

  return {
    sourcePath,
    outputPath,
    slug,
    title,
    date: typeof data.date === 'string' ? data.date : undefined,
    tags,
    html: marked.parse(parsed.content),
  };
}

async function markdownFiles(directory: string): Promise<string[]> {
  const entries = await readdir(directory, { withFileTypes: true });
  const files = await Promise.all(entries.map((entry) => {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) return markdownFiles(path);
    return entry.isFile() && /\.md$/i.test(entry.name) ? Promise.resolve([path]) : Promise.resolve([]);
  }));
  return files.flat();
}

function renderPage(page: Page): string {
  return `<!doctype html>\n<html lang="en">\n<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>${escapeHtml(page.title)}</title></head>\n<body>\n<article>\n<h1>${escapeHtml(page.title)}</h1>${page.date ? `\n<time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : ''}${page.tags.length ? `\n<p>Tags: ${page.tags.map(escapeHtml).join(', ')}</p>` : ''}\n${page.html}\n</article>\n</body>\n</html>\n`;
}

function renderIndex(pages: Page[]): string {
  const items = pages.map((page) => `<li><a href="${escapeHtml(`${page.slug}.html`)}">${escapeHtml(page.title)}</a>${page.date ? ` <time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : ''}</li>`).join('\n');
  return `<!doctype html>\n<html lang="en">\n<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Pages</title></head>\n<body>\n<h1>Pages</h1>\n<ul>\n${items}\n</ul>\n</body>\n</html>\n`;
}

export async function buildSite(options: BuildOptions = {}): Promise<Page[]> {
  const contentDir = resolve(options.contentDir ?? 'content');
  const outputDir = resolve(options.outputDir ?? 'dist');
  const files = await markdownFiles(contentDir);
  const pages = await Promise.all(files.map(async (sourcePath) => parsePage(await readFile(sourcePath, 'utf8'), sourcePath, contentDir, outputDir)));
  pages.sort((a, b) => a.title.localeCompare(b.title));

  await rm(outputDir, { recursive: true, force: true });
  await mkdir(outputDir, { recursive: true });
  await Promise.all(pages.map(async (page) => {
    await mkdir(dirname(page.outputPath), { recursive: true });
    await writeFile(page.outputPath, renderPage(page), 'utf8');
  }));
  await writeFile(join(outputDir, 'index.html'), renderIndex(pages), 'utf8');
  return pages;
}
