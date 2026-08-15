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

export interface ParsedMarkdown {
  data: Frontmatter;
  content: string;
}

const markdownExtensions = new Set(['.md', '.markdown']);

function parseSimpleYaml(input: string): Frontmatter {
  const data: Frontmatter = {};
  for (const line of input.split(/\r?\n/)) {
    const separator = line.indexOf(':');
    if (separator < 0) continue;
    const key = line.slice(0, separator).trim();
    if (!key) continue;
    let value = line.slice(separator + 1).trim();
    if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) {
      value = value.slice(1, -1);
    }
    if (value.startsWith('[') && value.endsWith(']')) {
      data[key] = value.slice(1, -1).split(',').map((tag) => tag.trim().replace(/^['"]|['"]$/g, '')).filter(Boolean);
    } else {
      data[key] = value;
    }
  }
  return data;
}

export function parseMarkdown(source: string): ParsedMarkdown {
  let yaml: Frontmatter = {};
  let markdown = source;
  const match = source.match(/^---\s*\r?\n([\s\S]*?)\r?\n---\s*(?:\r?\n|$)/);
  if (match) {
    yaml = parseSimpleYaml(match[1]);
    markdown = source.slice(match[0].length);
  }

  // gray-matter still owns the document representation; custom YAML is merged
  // afterward because this project intentionally does not depend on a YAML engine.
  const parsed = matter(markdown);
  return { data: { ...parsed.data, ...yaml } as Frontmatter, content: parsed.content };
}

function escapeHtml(value: string): string {
  return value.replace(/[&<>"']/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[character] as string);
}

function titleFor(filePath: string, data: Frontmatter): string {
  if (typeof data.title === 'string' && data.title.trim()) return data.title.trim();
  return path.basename(filePath, path.extname(filePath)).replace(/[-_]+/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function tagsFor(data: Frontmatter): string[] {
  if (Array.isArray(data.tags)) return data.tags.map(String);
  if (typeof data.tags === 'string') return data.tags.split(',').map((tag) => tag.trim()).filter(Boolean);
  return [];
}

async function markdownFiles(directory: string, relative = ''): Promise<string[]> {
  const entries = await fs.readdir(path.join(directory, relative), { withFileTypes: true });
  const files: string[] = [];
  for (const entry of entries) {
    const child = path.join(relative, entry.name);
    if (entry.isDirectory()) files.push(...await markdownFiles(directory, child));
    else if (markdownExtensions.has(path.extname(entry.name).toLowerCase())) files.push(child);
  }
  return files.sort();
}

function pageTemplate(page: Page): string {
  return `<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n<title>${escapeHtml(page.title)}</title>\n</head>\n<body>\n<main>\n<h1>${escapeHtml(page.title)}</h1>\n${page.date ? `<time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>\n` : ''}${page.tags.length ? `<p class="tags">${page.tags.map((tag) => `<span>${escapeHtml(tag)}</span>`).join(' ')}</p>\n` : ''}${page.html}\n</main>\n</body>\n</html>\n`;
}

function indexTemplate(pages: Page[]): string {
  const items = pages.map((page) => `<li><a href="${escapeHtml(page.outputPath)}">${escapeHtml(page.title)}</a>${page.date ? ` <time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : ''}</li>`).join('\n');
  return `<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n<title>Index</title>\n</head>\n<body>\n<main>\n<h1>Index</h1>\n<ul>\n${items}\n</ul>\n</main>\n</body>\n</html>\n`;
}

export async function buildSite(options: BuildOptions = {}): Promise<Page[]> {
  const contentDir = path.resolve(options.contentDir ?? './content');
  const outputDir = path.resolve(options.outputDir ?? './dist');
  const files = await markdownFiles(contentDir);
  const pages: Page[] = [];
  for (const relativeSource of files) {
    const source = await fs.readFile(path.join(contentDir, relativeSource), 'utf8');
    const parsed = parseMarkdown(source);
    const outputPath = relativeSource.replace(/\.(md|markdown)$/i, '.html').split(path.sep).join('/');
    const page: Page = {
      sourcePath: relativeSource.split(path.sep).join('/'),
      outputPath,
      title: titleFor(relativeSource, parsed.data),
      date: typeof parsed.data.date === 'string' ? parsed.data.date : undefined,
      tags: tagsFor(parsed.data),
      html: await marked.parse(parsed.content),
    };
    pages.push(page);
  }
  pages.sort((a, b) => (b.date ?? '').localeCompare(a.date ?? '') || a.outputPath.localeCompare(b.outputPath));
  await fs.rm(outputDir, { recursive: true, force: true });
  await fs.mkdir(outputDir, { recursive: true });
  for (const page of pages) {
    const destination = path.join(outputDir, page.outputPath);
    await fs.mkdir(path.dirname(destination), { recursive: true });
    await fs.writeFile(destination, pageTemplate(page), 'utf8');
  }
  await fs.writeFile(path.join(outputDir, 'index.html'), indexTemplate(pages), 'utf8');
  return pages;
}

export function parseArgs(args: string[]): BuildOptions {
  const options: BuildOptions = {};
  for (let index = 0; index < args.length; index += 1) {
    if (args[index] === '--content' || args[index] === '--output') {
      const value = args[++index];
      if (!value) throw new Error(`${args[index - 1]} requires a directory`);
      if (args[index - 1] === '--content') options.contentDir = value;
      else options.outputDir = value;
    }
  }
  return options;
}

export async function main(args = process.argv.slice(2)): Promise<void> {
  if (args[0] !== 'build') throw new Error('Usage: ssg build [--content <dir>] [--output <dir>]');
  await buildSite(parseArgs(args.slice(1)));
}

if (require.main === module) {
  main().catch((error: unknown) => {
    console.error(error instanceof Error ? error.message : error);
    process.exitCode = 1;
  });
}
