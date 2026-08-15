import fs from 'node:fs/promises';
import path from 'node:path';
import { marked } from 'marked';
import { parseMarkdown, Frontmatter } from './parser';

export interface BuildOptions {
  contentDir?: string;
  outputDir?: string;
  templatesDir?: string;
  defaultTemplate?: string;
}

interface Page {
  source: string;
  url: string;
  data: Frontmatter;
  html: string;
}

function escapeHtml(value: unknown): string {
  return String(value ?? '').replace(/[&<>"']/g, (character) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[character] as string));
}

function documentHtml(title: string, body: string): string {
  return `<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n<title>${escapeHtml(title)}</title>\n</head>\n<body>\n${body}\n</body>\n</html>\n`;
}

type TemplateContext = Record<string, unknown>;

function contextValue(context: TemplateContext, key: string): unknown {
  return key.split('.').reduce<unknown>((value, part) => {
    if (value && typeof value === 'object') return (value as Record<string, unknown>)[part];
    return undefined;
  }, context);
}

function templateNameCandidates(name: string): string[] {
  if (path.extname(name)) return [name];
  return [`${name}.hbs`, `${name}.ejs`];
}

async function readTemplate(directory: string, name: string, subdirectory = ''): Promise<{ source: string; extension: string } | undefined> {
  for (const candidate of templateNameCandidates(name)) {
    const file = path.join(directory, subdirectory, candidate);
    try {
      return { source: await fs.readFile(file, 'utf8'), extension: path.extname(file).toLowerCase() };
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code !== 'ENOENT') throw error;
    }
  }
  return undefined;
}

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

function renderTemplate(source: string, context: TemplateContext, partials: Map<string, string>): string {
  const value = (key: string): string => String(contextValue(context, key.trim()) ?? '');
  const partial = (name: string): string => {
    const key = name.trim().replace(/^partials\//, '').replace(/\.(?:hbs|ejs)$/i, '');
    const source = partials.get(key);
    return source ? renderTemplate(source, context, partials) : '';
  };

  let rendered = source.replace(/{{{\s*([^{}]+?)\s*}}}/g, (_, key: string) => value(key));
  rendered = rendered.replace(/{{>\s*([^{}]+?)\s*}}/g, (_, name: string) => partial(name));
  rendered = rendered.replace(/{{\s*([^{}]+?)\s*}}/g, (_, key: string) => escapeHtml(value(key)));
  rendered = rendered.replace(/<%[-=]\s*include\(\s*['"]([^'"]+)['"]\s*\)\s*%>/g, (_, name: string) => partial(name));
  rendered = rendered.replace(/<%=\s*([^%]+?)\s*%>/g, (_, key: string) => escapeHtml(value(key)));
  rendered = rendered.replace(/<%-\s*([^%]+?)\s*%>/g, (_, key: string) => value(key));
  return rendered;
}

async function loadPartials(directory: string): Promise<Map<string, string>> {
  const partials = new Map<string, string>();
  for (const file of await templateFiles(path.join(directory, 'partials'))) {
    const relative = path.relative(path.join(directory, 'partials'), file);
    partials.set(relative.replace(/\.(?:hbs|ejs)$/i, '').split(path.sep).join('/'), await fs.readFile(file, 'utf8'));
  }
  return partials;
}

async function renderPage(
  templatesDir: string,
  data: Frontmatter,
  context: TemplateContext,
  fallback: string,
  partials: Map<string, string>,
): Promise<string> {
  const requestedTemplate = typeof data.template === 'string' ? data.template : undefined;
  const template = requestedTemplate ? await readTemplate(templatesDir, requestedTemplate) : undefined;
  if (requestedTemplate && !template) throw new Error(`Template not found: ${requestedTemplate}`);
  const defaultTemplate = template ? undefined : await readTemplate(templatesDir, fallback);
  let rendered = renderTemplate((template ?? defaultTemplate)?.source ?? String(context.body), context, partials);
  const layoutName = typeof data.layout === 'string' ? data.layout : undefined;
  if (layoutName) {
    const layout = await readTemplate(templatesDir, layoutName, 'layouts');
    if (!layout) throw new Error(`Template not found: layouts/${layoutName}`);
    rendered = renderTemplate(layout.source, { ...context, body: rendered }, partials);
  }
  return rendered;
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

export async function buildSite(options: BuildOptions = {}): Promise<void> {
  const contentDir = path.resolve(options.contentDir ?? './content');
  const outputDir = path.resolve(options.outputDir ?? './dist');
  const templatesDir = path.resolve(options.templatesDir ?? './templates');
  const defaultTemplate = options.defaultTemplate ?? 'default';
  const partials = await loadPartials(templatesDir);
  const files = await markdownFiles(contentDir);
  const pages: Page[] = [];

  await fs.rm(outputDir, { recursive: true, force: true });
  await fs.mkdir(outputDir, { recursive: true });
  for (const source of files) {
    const parsed = parseMarkdown(await fs.readFile(source, 'utf8'));
    const relative = path.relative(contentDir, source);
    const url = relative.replace(/\.md$/i, '.html').split(path.sep).join('/');
    const title = typeof parsed.data.title === 'string' ? parsed.data.title : path.basename(relative, path.extname(relative));
    const tags = Array.isArray(parsed.data.tags) ? parsed.data.tags : [];
    const metadata = [parsed.data.date ? `<time>${escapeHtml(parsed.data.date)}</time>` : '', tags.length ? `<p class="tags">${tags.map(escapeHtml).join(', ')}</p>` : ''].join('');
    const body = `<article>\n<h1>${escapeHtml(title)}</h1>\n${metadata}\n${marked.parse(parsed.content)}\n</article>`;
    const context: TemplateContext = { ...parsed.data, title, url, body, content: parsed.content, html: marked.parse(parsed.content) };
    const rendered = await renderPage(templatesDir, parsed.data, context, defaultTemplate, partials);
    const destination = path.join(outputDir, url);
    await fs.mkdir(path.dirname(destination), { recursive: true });
    const hasCustomTemplate = typeof parsed.data.template === 'string'
      || typeof parsed.data.layout === 'string'
      || Boolean(await readTemplate(templatesDir, defaultTemplate));
    await fs.writeFile(destination, hasCustomTemplate || rendered.match(/^\s*<!doctype html>/i) ? rendered : documentHtml(title, rendered), 'utf8');
    pages.push({ source, url, data: parsed.data, html: body });
  }

  const listing = pages.map((page) => {
    const title = typeof page.data.title === 'string' ? page.data.title : path.basename(page.url, '.html');
    return `<li><a href="${escapeHtml(page.url)}">${escapeHtml(title)}</a></li>`;
  }).join('\n');
  await fs.writeFile(path.join(outputDir, 'index.html'), documentHtml('Index', `<main>\n<h1>Pages</h1>\n<ul>\n${listing}\n</ul>\n</main>`), 'utf8');
}
