import fs from 'node:fs/promises';
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
  slug: string;
  source: string;
  title: string;
  date?: string;
  tags: string[];
  html: string;
  template?: string;
  layout?: string;
}

function parseScalar(value: string): unknown {
  const trimmed = value.trim();
  if (!trimmed) return '';
  if ((trimmed.startsWith('[') && trimmed.endsWith(']'))) {
    return trimmed.slice(1, -1).split(',').map((item) => item.trim()).filter(Boolean);
  }
  if ((trimmed.startsWith('"') && trimmed.endsWith('"')) || (trimmed.startsWith("'") && trimmed.endsWith("'"))) {
    return trimmed.slice(1, -1);
  }
  return trimmed;
}

function parseYamlFrontmatter(source: string): { data: Frontmatter; content: string } | undefined {
  if (!source.startsWith('---')) return undefined;
  const match = source.match(/^---\s*\r?\n([\s\S]*?)\r?\n---\s*\r?\n?/);
  if (!match) return undefined;
  const json = match[1].trim();
  if (json.startsWith('{')) {
    const parsed = matter(source);
    return { data: parsed.data as Frontmatter, content: parsed.content };
  }
  const data: Frontmatter = {};
  for (const line of match[1].split(/\r?\n/)) {
    const separator = line.indexOf(':');
    if (separator < 0) continue;
    const key = line.slice(0, separator).trim();
    if (key) data[key] = parseScalar(line.slice(separator + 1));
  }
  return { data, content: source.slice(match[0].length) };
}

export function parseMarkdown(source: string, sourcePath = 'page.md'): Page {
  const yaml = parseYamlFrontmatter(source);
  const parsed = yaml ? { data: yaml.data, content: matter(yaml.content).content } : matter(source);
  const data = parsed.data as Frontmatter;
  const basename = path.basename(sourcePath, path.extname(sourcePath));
  const tags = Array.isArray(data.tags) ? data.tags.map(String) : data.tags ? String(data.tags).split(',').map((tag) => tag.trim()).filter(Boolean) : [];
  return {
    slug: basename,
    source: sourcePath,
    title: data.title ? String(data.title) : basename,
    date: data.date ? String(data.date) : undefined,
    tags,
    template: data.template ? String(data.template) : undefined,
    layout: data.layout ? String(data.layout) : undefined,
    html: String(marked.parse(parsed.content)),
  };
}

async function markdownFiles(directory: string): Promise<string[]> {
  const entries = await fs.readdir(directory, { withFileTypes: true });
  const files: string[] = [];
  for (const entry of entries) {
    const fullPath = path.join(directory, entry.name);
    if (entry.isDirectory()) files.push(...await markdownFiles(fullPath));
    else if (/\.md$/i.test(entry.name)) files.push(fullPath);
  }
  return files.sort();
}

function escapeHtml(value: string): string {
  return value.replace(/[&<>"']/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[character]!));
}

function defaultLayout(title: string, body: string): string {
  return `<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n<title>${escapeHtml(title)}</title>\n</head>\n<body>\n${body}\n</body>\n</html>\n`;
}

type TemplateValues = Record<string, unknown>;

async function templateFiles(directory: string): Promise<string[]> {
  try {
    const entries = await fs.readdir(directory, { withFileTypes: true });
    const files: string[] = [];
    for (const entry of entries) {
      const fullPath = path.join(directory, entry.name);
      if (entry.isDirectory()) files.push(...await templateFiles(fullPath));
      else if (/\.(?:hbs|ejs)$/i.test(entry.name)) files.push(fullPath);
    }
    return files;
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return [];
    throw error;
  }
}

function value(context: TemplateValues, key: string): unknown {
  return key.split('.').reduce<unknown>((current, part) => {
    if (current && typeof current === 'object') return (current as Record<string, unknown>)[part];
    return undefined;
  }, context);
}

function renderHandlebars(source: string, context: TemplateValues, partials: Map<string, string>): string {
  const render = (input: string, localContext: TemplateValues): string => {
    let result = input.replace(/{{#each\s+([^}]+)}}([\s\S]*?){{\/each}}/g, (_match, key: string, body: string) => {
      const items = value(localContext, key.trim());
      if (!Array.isArray(items)) return '';
      return items.map((item) => render(body, { ...localContext, this: item, '@index': items.indexOf(item) })).join('');
    });
    result = result.replace(/{{#if\s+([^}]+)}}([\s\S]*?){{\/if}}/g, (_match, key: string, body: string) => value(localContext, key.trim()) ? render(body, localContext) : '');
    result = result.replace(/{{>\s*([\w./-]+)\s*}}/g, (_match, name: string) => {
      const partialName = name.replace(/^partials\//, '');
      const partial = partials.get(partialName) ?? partials.get(`${partialName}.hbs`) ?? '';
      return render(partial, localContext);
    });
    result = result.replace(/{{{\s*([^}]+)\s*}}}/g, (_match, key: string) => String(value(localContext, key.trim()) ?? ''));
    return result.replace(/{{\s*([^}]+)\s*}}/g, (_match, key: string) => escapeHtml(String(value(localContext, key.trim()) ?? '')));
  };
  return render(source, context);
}

function renderEjs(source: string, context: TemplateValues, partials: Map<string, string>): string {
  const include = (name: string): string => {
    const normalized = name.replace(/^\.\//, '').replace(/^partials\//, '').replace(/\.(?:hbs|ejs)$/i, '');
    return partials.get(normalized) ?? partials.get(name) ?? '';
  };
  const evaluate = (expression: string): unknown => value(context, expression.trim()) ?? (expression.trim() === 'this' ? context.this : undefined);
  let result = source.replace(/<%[-=]\s*include\(['"]([^'"]+)['"]\)\s*%>/g, (_match, name: string) => renderEjs(include(name), context, partials));
  result = result.replace(/<%-\s*([^%]+?)\s*%>/g, (_match, expression: string) => String(evaluate(expression) ?? ''));
  return result.replace(/<%=\s*([^%]+?)\s*%>/g, (_match, expression: string) => escapeHtml(String(evaluate(expression) ?? '')));
}

async function createRenderer(templatesDir: string): Promise<(page: Page, body: string) => Promise<string>> {
  const files = await templateFiles(templatesDir);
  const templates = new Map<string, { source: string; extension: string }>();
  const partials = new Map<string, string>();
  for (const file of files) {
    const relative = path.relative(templatesDir, file).split(path.sep).join('/');
    const name = relative.replace(/\.(?:hbs|ejs)$/i, '');
    const source = await fs.readFile(file, 'utf8');
    if (name.startsWith('partials/')) partials.set(name.slice('partials/'.length), source);
    else templates.set(name, { source, extension: path.extname(file) });
  }
  const render = (source: string, context: TemplateValues, extension: string): string => extension === '.ejs' ? renderEjs(source, context, partials) : renderHandlebars(source, context, partials);
  const find = (name: string, directory = ''): { source: string; extension: string } | undefined => {
    const normalized = name.replace(/^\.?\//, '').replace(/\.(?:hbs|ejs)$/i, '');
    const template = templates.get(`${directory}${normalized}`);
    if (template) return template;
    return undefined;
  };
  return async (page, body) => {
    const context: TemplateValues = { ...page, body, content: page.html };
    const selected = page.template ? find(page.template) : find('default');
    let rendered = selected ? render(selected.source, context, selected.extension) : body;
    const layoutName = page.layout === undefined ? 'default' : page.layout;
    if (layoutName !== 'false') {
      const layout = find(String(layoutName), 'layouts/');
      if (layout) rendered = render(layout.source, { ...context, body: rendered, content: rendered }, layout.extension);
      else if (!selected) rendered = defaultLayout(page.title, rendered);
    }
    return rendered;
  };
}

export async function buildSite(contentDir = './content', outputDir = './dist', templatesDir = './templates'): Promise<Page[]> {
  const files = await markdownFiles(contentDir);
  const pages = await Promise.all(files.map(async (file) => parseMarkdown(await fs.readFile(file, 'utf8'), path.relative(contentDir, file))));
  pages.sort((a, b) => (b.date || '').localeCompare(a.date || '') || a.title.localeCompare(b.title));
  await fs.mkdir(outputDir, { recursive: true });
  const renderPage = await createRenderer(templatesDir);
  await Promise.all(pages.map(async (page) => {
    const body = `<main>\n<h1>${escapeHtml(page.title)}</h1>\n${page.html}\n</main>`;
    await fs.writeFile(path.join(outputDir, `${page.slug}.html`), await renderPage(page, body));
  }));
  const links = pages.map((page) => `<li><a href="${encodeURIComponent(page.slug)}.html">${escapeHtml(page.title)}</a>${page.date ? ` <time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : ''}</li>`).join('\n');
  const indexPage: Page = { slug: 'index', source: 'index.md', title: 'Home', tags: [], html: '', template: undefined };
  await fs.writeFile(path.join(outputDir, 'index.html'), await renderPage(indexPage, `<main>\n<h1>Pages</h1>\n<ul>\n${links}\n</ul>\n</main>`));
  return pages;
}
