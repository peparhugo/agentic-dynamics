import { promises as fs, type Dirent } from 'node:fs';
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
  templatesDir?: string;
}

type TemplateContext = Record<string, unknown>;

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

function templateValue(context: TemplateContext, key: string): unknown {
  if (key === 'this' || key === '.') return context.this;
  const parts = key.split('.');
  let value: unknown = context;
  for (const part of parts) {
    if (value == null || typeof value !== 'object') return undefined;
    value = (value as Record<string, unknown>)[part];
  }
  return value;
}

function renderTemplate(source: string, context: TemplateContext, partials: Map<string, string>): string {
  let rendered = source.replace(/{{!--[\s\S]*?--}}|{{!.*?}}/g, '');
  const block = /{{#(if|unless|each)\s+([^}]+)}}([\s\S]*?){{\/\1}}/g;

  while (block.test(rendered)) {
    block.lastIndex = 0;
    rendered = rendered.replace(block, (_match, helper: string, key: string, contents: string) => {
      const [truthy, falsy = ''] = contents.split('{{else}}');
      const value = templateValue(context, key.trim());
      if (helper === 'each') {
        return Array.isArray(value)
          ? value.map((item, index) => renderTemplate(truthy, {
            ...context,
            this: item,
            '@index': index,
          }, partials)).join('')
          : '';
      }
      const useTruthy = helper === 'unless' ? !value : Boolean(value);
      return renderTemplate(useTruthy ? truthy : falsy, context, partials);
    });
  }

  rendered = rendered.replace(/{{>\s*([^\s}]+)\s*}}/g, (_match, name: string) => {
    const partial = partials.get(name);
    if (partial == null) throw new Error(`Unknown template partial: ${name}`);
    return renderTemplate(partial, context, partials);
  });
  rendered = rendered.replace(/{{{\s*([^}]+?)\s*}}}/g, (_match, key: string) => {
    const value = templateValue(context, key.trim());
    return value == null ? '' : String(value);
  });
  return rendered.replace(/{{\s*([^#/!>][^}]*?)\s*}}/g, (_match, key: string) => {
    const value = templateValue(context, key.trim());
    return value == null ? '' : escapeHtml(String(value));
  });
}

function safeTemplatePath(directory: string, name: string): string {
  const withExtension = path.extname(name) ? name : `${name}.hbs`;
  const resolved = path.resolve(directory, withExtension);
  const relative = path.relative(directory, resolved);
  if (relative === '..' || relative.startsWith(`..${path.sep}`) || path.isAbsolute(relative)) {
    throw new Error(`Template path must stay inside ${directory}: ${name}`);
  }
  return resolved;
}

async function optionalFile(filePath: string): Promise<string | undefined> {
  try {
    return await fs.readFile(filePath, 'utf8');
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return undefined;
    throw error;
  }
}

async function loadPartials(directory: string): Promise<Map<string, string>> {
  const partials = new Map<string, string>();
  let entries: Dirent[];
  try {
    entries = await fs.readdir(directory, { withFileTypes: true });
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return partials;
    throw error;
  }

  await Promise.all(entries.map(async (entry) => {
    const entryPath = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      const nested = await loadPartials(entryPath);
      for (const [name, source] of nested) partials.set(`${entry.name}/${name}`, source);
    } else if (entry.isFile() && /\.hbs$/i.test(entry.name)) {
      const name = entry.name.replace(/\.hbs$/i, '');
      partials.set(name, await fs.readFile(entryPath, 'utf8'));
    }
  }));
  return partials;
}

async function renderPageTemplate(
  page: GeneratedPage,
  pages: GeneratedPage[],
  templatesDir: string,
  partials: Map<string, string>,
): Promise<string> {
  const requestedTemplate = typeof page.data.template === 'string' ? page.data.template : 'default';
  const templatePath = safeTemplatePath(templatesDir, requestedTemplate);
  const template = await optionalFile(templatePath);
  if (template == null) {
    if (page.data.template != null) throw new Error(`Template not found: ${requestedTemplate}`);
    return renderPage(page);
  }

  const context: TemplateContext = {
    ...page.data,
    data: page.data,
    page,
    pages,
    title: page.title,
    content: page.html,
    html: page.html,
    url: page.url,
  };
  const body = renderTemplate(template, context, partials);
  if (page.data.layout === false || page.data.layout === null) return body;

  const requestedLayout = typeof page.data.layout === 'string' ? page.data.layout : 'default';
  const layoutPath = safeTemplatePath(path.join(templatesDir, 'layouts'), requestedLayout);
  const layout = await optionalFile(layoutPath);
  if (layout == null) {
    if (page.data.layout != null) throw new Error(`Layout not found: ${requestedLayout}`);
    return body;
  }
  return renderTemplate(layout, { ...context, body }, partials);
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
  const templatesDir = path.resolve(options.templatesDir ?? './templates');
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
  const partials = await loadPartials(path.join(templatesDir, 'partials'));
  await Promise.all(pages.map(async (page) => {
    await fs.mkdir(path.dirname(page.outputPath), { recursive: true });
    await fs.writeFile(page.outputPath, await renderPageTemplate(page, pages, templatesDir, partials), 'utf8');
  }));
  await fs.writeFile(path.join(outputDir, 'index.html'), renderIndex(pages), 'utf8');
  return pages;
}
