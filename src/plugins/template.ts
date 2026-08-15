import { promises as fs, type Dirent } from 'node:fs';
import path from 'node:path';
import type { BuildContext, GeneratedPage, Plugin } from '../types';

type TemplateContext = Record<string, unknown>;

export function escapeHtml(value: string): string {
  return value.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;').replaceAll("'", '&#39;');
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
    ? `<ul class="tags">${page.data.tags.map((tag) => `<li>${escapeHtml(tag)}</li>`).join('')}</ul>` : '';
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
  let value: unknown = context;
  for (const part of key.split('.')) {
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
        return Array.isArray(value) ? value.map((item, index) => renderTemplate(truthy, {
          ...context, this: item, '@index': index,
        }, partials)).join('') : '';
      }
      return renderTemplate((helper === 'unless' ? !value : Boolean(value)) ? truthy : falsy, context, partials);
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
  const resolved = path.resolve(directory, path.extname(name) ? name : `${name}.hbs`);
  const relative = path.relative(directory, resolved);
  if (relative === '..' || relative.startsWith(`..${path.sep}`) || path.isAbsolute(relative)) {
    throw new Error(`Template path must stay inside ${directory}: ${name}`);
  }
  return resolved;
}

async function optionalFile(filePath: string): Promise<string | undefined> {
  try { return await fs.readFile(filePath, 'utf8'); } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return undefined;
    throw error;
  }
}

async function loadPartials(directory: string): Promise<Map<string, string>> {
  const partials = new Map<string, string>();
  let entries: Dirent[];
  try { entries = await fs.readdir(directory, { withFileTypes: true }); } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return partials;
    throw error;
  }
  await Promise.all(entries.map(async (entry) => {
    const entryPath = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      for (const [name, source] of await loadPartials(entryPath)) partials.set(`${entry.name}/${name}`, source);
    } else if (entry.isFile() && /\.hbs$/i.test(entry.name)) {
      partials.set(entry.name.replace(/\.hbs$/i, ''), await fs.readFile(entryPath, 'utf8'));
    }
  }));
  return partials;
}

async function renderPageTemplate(page: GeneratedPage, pages: GeneratedPage[], templatesDir: string,
  partials: Map<string, string>): Promise<string> {
  const requestedTemplate = typeof page.data.template === 'string' ? page.data.template : 'default';
  const template = await optionalFile(safeTemplatePath(templatesDir, requestedTemplate));
  if (template == null) {
    if (page.data.template != null) throw new Error(`Template not found: ${requestedTemplate}`);
    return renderPage(page);
  }
  const context: TemplateContext = {
    ...page.data, data: page.data, page, pages, title: page.title, content: page.html, html: page.html, url: page.url,
  };
  const body = renderTemplate(template, context, partials);
  if (page.data.layout === false || page.data.layout === null) return body;
  const requestedLayout = typeof page.data.layout === 'string' ? page.data.layout : 'default';
  const layout = await optionalFile(safeTemplatePath(path.join(templatesDir, 'layouts'), requestedLayout));
  if (layout == null) {
    if (page.data.layout != null) throw new Error(`Layout not found: ${requestedLayout}`);
    return body;
  }
  return renderTemplate(layout, { ...context, body }, partials);
}

export class TemplatePlugin implements Plugin {
  readonly name = 'templates';
  private partials = new Map<string, string>();

  async beforeBuild(context: BuildContext): Promise<void> {
    await fs.rm(context.options.outputDir, { recursive: true, force: true });
    await fs.mkdir(context.options.outputDir, { recursive: true });
    this.partials = await loadPartials(path.join(context.options.templatesDir, 'partials'));
  }

  async afterBuild(context: BuildContext): Promise<void> {
    await Promise.all(context.pages.map(async (page) => {
      await fs.mkdir(path.dirname(page.outputPath), { recursive: true });
      const html = await renderPageTemplate(page, context.pages, context.options.templatesDir, this.partials);
      await fs.writeFile(page.outputPath, html, 'utf8');
    }));
    await fs.writeFile(path.join(context.options.outputDir, 'index.html'), renderIndex(context.pages), 'utf8');
  }
}
