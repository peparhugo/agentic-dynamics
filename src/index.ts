import matter from 'gray-matter';
import { marked } from 'marked';
import { promises as fs } from 'node:fs';
import path from 'node:path';

export interface Page {
  title: string;
  date?: string;
  tags: string[];
  slug: string;
  html: string;
  sourcePath: string;
  template?: string;
  layout?: string;
  data?: Record<string, unknown>;
}

export interface BuildOptions {
  contentDir?: string;
  outputDir?: string;
  templatesDir?: string;
  defaultTemplate?: string;
}

function escapeHtml(value: string): string {
  return value.replace(/[&<>"']/g, (character) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[character] as string);
}

function normaliseTags(value: unknown): string[] {
  if (Array.isArray(value)) return value.map(String);
  if (typeof value === 'string') return value.split(',').map((tag) => tag.trim()).filter(Boolean);
  return [];
}

function normaliseDate(value: unknown): string | undefined {
  if (value === undefined || value === null) return undefined;
  if (value instanceof Date) return value.toISOString().slice(0, 10);
  return String(value);
}

export async function parseMarkdown(source: string, sourcePath = 'page.md'): Promise<Page> {
  const parsed = matter(source);
  const name = path.basename(sourcePath, path.extname(sourcePath));
  const title = typeof parsed.data.title === 'string' && parsed.data.title.trim()
    ? parsed.data.title.trim()
    : name.replace(/[-_]+/g, ' ');
  const date = normaliseDate(parsed.data.date);

  return {
    title,
    date,
    tags: normaliseTags(parsed.data.tags),
    slug: `${name}.html`,
    html: await marked.parse(parsed.content),
    sourcePath,
    template: typeof parsed.data.template === 'string' ? parsed.data.template : undefined,
    layout: typeof parsed.data.layout === 'string' ? parsed.data.layout : undefined,
    data: parsed.data as Record<string, unknown>
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

function document(title: string, body: string): string {
  return `<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n<title>${escapeHtml(title)}</title>\n</head>\n<body>\n${body}\n</body>\n</html>\n`;
}

type TemplateContext = Record<string, unknown>;

function lookup(context: TemplateContext, key: string): unknown {
  return key.trim().split('.').reduce<unknown>((value, part) => {
    if (value && typeof value === 'object') return (value as Record<string, unknown>)[part];
    return undefined;
  }, context);
}

function templateValue(value: unknown): string {
  return value === undefined || value === null ? '' : String(value);
}

function handlebars(template: string, context: TemplateContext, partials: Map<string, string>): string {
  let result = template.replace(/{{>\s*([\w./-]+)\s*}}/g, (_match, name: string) => {
    const partial = partials.get(name) ?? partials.get(name.replace(/\.(?:hbs|ejs)$/i, ''));
    return partial === undefined ? '' : handlebars(partial, context, partials);
  });
  // Repeatedly resolve blocks so nested if/each constructs work for normal templates.
  let previous: string;
  do {
    previous = result;
    result = result.replace(/{{#if\s+([^}]+)}}([\s\S]*?){{\/if}}/g, (_match, key: string, content: string) =>
      lookup(context, key) ? content : '');
    result = result.replace(/{{#each\s+([^}]+)}}([\s\S]*?){{\/each}}/g, (_match, key: string, content: string) => {
      const values = lookup(context, key);
      if (!Array.isArray(values)) return '';
      return values.map((value) => handlebars(content, { ...context, this: value, ...(typeof value === 'object' && value ? value : {}) }, partials)).join('');
    });
  } while (result !== previous);
  result = result.replace(/{{{\s*([^}]+)\s*}}}/g, (_match, key: string) => templateValue(lookup(context, key)));
  return result.replace(/{{\s*([^#/>][^}]*)\s*}}/g, (_match, key: string) => escapeHtml(templateValue(lookup(context, key))));
}

function ejs(template: string, context: TemplateContext, partials: Map<string, string>): string {
  const include = (name: string): string => {
    const key = name.replace(/^partials\//, '').replace(/\.(?:hbs|ejs)$/i, '');
    const partial = partials.get(key) ?? partials.get(name);
    return partial === undefined ? '' : ejs(partial, context, partials);
  };
  return template.replace(/<%([=-])?([\s\S]*?)%>/g, (_match, mode: string | undefined, expression: string) => {
    const code = expression.trim();
    if (code.startsWith('include(')) {
      const name = code.match(/include\(\s*['"]([^'"]+)['"]\s*\)/)?.[1];
      return name ? include(name) : '';
    }
    if (mode === '=' || mode === '-') {
      try {
        const value = Function('context', `with (context) { return (${code}); }`)(context);
        return mode === '=' ? escapeHtml(templateValue(value)) : templateValue(value);
      } catch { return ''; }
    }
    return '';
  });
}

async function findTemplate(directory: string, requested: string, category?: string): Promise<{ source: string; extension: string } | undefined> {
  const name = requested.replace(/^[/\\]+/, '').replace(/\.(hbs|ejs)$/i, '');
  const base = category ? path.join(directory, category, name) : path.join(directory, name);
  for (const extension of ['.hbs', '.ejs']) {
    const file = `${base}${extension}`;
    try { return { source: await fs.readFile(file, 'utf8'), extension }; } catch { /* try next supported engine */ }
  }
  return undefined;
}

async function loadPartials(directory: string): Promise<Map<string, string>> {
  const partials = new Map<string, string>();
  const partialDir = path.join(directory, 'partials');
  const entries = await (async () => { try { return await fs.readdir(partialDir, { withFileTypes: true }); } catch { return []; } })();
  for (const entry of entries) {
    if (entry.isFile() && /\.(hbs|ejs)$/i.test(entry.name)) {
      partials.set(entry.name.replace(/\.(hbs|ejs)$/i, ''), await fs.readFile(path.join(partialDir, entry.name), 'utf8'));
    }
  }
  return partials;
}

function renderTemplate(source: string, extension: string, context: TemplateContext, partials: Map<string, string>): string {
  return extension === '.ejs' ? ejs(source, context, partials) : handlebars(source, context, partials);
}

export async function buildSite(options: BuildOptions = {}): Promise<Page[]> {
  const contentDir = path.resolve(options.contentDir ?? './content');
  const outputDir = path.resolve(options.outputDir ?? './dist');
  const templatesDir = path.resolve(options.templatesDir ?? './templates');
  const files = await markdownFiles(contentDir);
  const pages = await Promise.all(files.map(async (file) => {
    const relative = path.relative(contentDir, file);
    const page = await parseMarkdown(await fs.readFile(file, 'utf8'), relative);
    page.slug = `${relative.replace(/\.md$/i, '')}.html`;
    page.sourcePath = relative;
    return page;
  }));

  await fs.rm(outputDir, { recursive: true, force: true });
  await fs.mkdir(outputDir, { recursive: true });
  const partials = await loadPartials(templatesDir);
  const defaultTemplate = options.defaultTemplate ?? 'default';
  await Promise.all(pages.map(async (page) => {
    const outputPath = path.join(outputDir, page.slug);
    await fs.mkdir(path.dirname(outputPath), { recursive: true });
    const metadata = [page.date ? `<p class="date">${escapeHtml(page.date)}</p>` : '', page.tags.length ? `<p class="tags">${page.tags.map(escapeHtml).join(', ')}</p>` : ''].join('');
    const content = `<main><h1>${escapeHtml(page.title)}</h1>${metadata}${page.html}</main>`;
    const context: TemplateContext = { ...(page.data ?? {}), ...page, content, body: content };
    const selected = await findTemplate(templatesDir, page.template ?? defaultTemplate);
    let body = selected ? renderTemplate(selected.source, selected.extension, context, partials) : content;
    const layoutName = page.layout ?? 'default';
    const layout = await findTemplate(templatesDir, layoutName, 'layouts');
    if (layout) body = renderTemplate(layout.source, layout.extension, { ...context, body }, partials);
    await fs.writeFile(outputPath, selected || layout ? body : document(page.title, body));
  }));

  const links = pages.map((page) => `<li><a href="${escapeHtml(page.slug)}">${escapeHtml(page.title)}</a>${page.date ? ` <time>${escapeHtml(page.date)}</time>` : ''}</li>`).join('\n');
  await fs.writeFile(path.join(outputDir, 'index.html'), document('Home', `<main><h1>Pages</h1><ul>${links}</ul></main>`));
  return pages;
}
