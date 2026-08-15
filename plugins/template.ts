import { promises as fs } from 'node:fs';
import path from 'node:path';
import type { Frontmatter, Page } from '../index';
import type { BuildContext, Plugin } from './types';

type TemplateContext = Record<string, unknown>;
type LoadedTemplates = { templates: Map<string, string>; partials: Map<string, string>; layouts: Map<string, string> };

function escapeHtml(value: string): string {
  return value.replace(/[&<>"']/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[character] as string);
}
function valueFor(context: TemplateContext, name: string): unknown { return name.split('.').reduce<unknown>((value, key) => value && typeof value === 'object' ? (value as Record<string, unknown>)[key] : undefined, context); }
function renderTemplate(source: string, context: TemplateContext, partials: Map<string, string>): string {
  let rendered = source;
  rendered = rendered.replace(/{{#each\s+([\w.]+)}}([\s\S]*?){{\/each}}/g, (_m, name: string, body: string) => {
    const values = valueFor(context, name);
    if (!Array.isArray(values)) return '';
    return values.map((item) => renderTemplate(body, { ...context, ...(item && typeof item === 'object' ? item as Record<string, unknown> : {}), this: item, '.': item }, partials)).join('');
  });
  rendered = rendered.replace(/{{#if\s+([\w.]+)}}([\s\S]*?){{\/if}}/g, (_m, name: string, body: string) => valueFor(context, name) ? renderTemplate(body, context, partials) : '');
  rendered = rendered.replace(/{{>\s*([\w./-]+)\s*}}/g, (_m, name: string) => { const partial = partials.get(name) ?? partials.get(name.replace(/\.hbs$|\.ejs$/i, '')); return partial ? renderTemplate(partial, context, partials) : ''; });
  rendered = rendered.replace(/{{{\s*([\w.$]+)\s*}}}/g, (_m, name: string) => String(valueFor(context, name) ?? ''));
  return rendered.replace(/{{\s*([\w.$]+)\s*}}/g, (_m, name: string) => escapeHtml(String(valueFor(context, name) ?? '')));
}
async function loadTemplates(directory: string): Promise<LoadedTemplates> {
  const result: LoadedTemplates = { templates: new Map(), partials: new Map(), layouts: new Map() };
  async function readDirectory(current: string, target: Map<string, string>, prefix = ''): Promise<void> {
    let entries;
    try { entries = await fs.readdir(current, { withFileTypes: true }); } catch (error: unknown) { if ((error as NodeJS.ErrnoException).code === 'ENOENT') return; throw error; }
    for (const entry of entries) {
      const fullPath = path.join(current, entry.name);
      if (entry.isDirectory()) await readDirectory(fullPath, target, prefix ? `${prefix}/${entry.name}` : entry.name);
      else if (/\.(hbs|ejs)$/i.test(entry.name)) { const name = `${prefix ? `${prefix}/` : ''}${entry.name}`; const content = await fs.readFile(fullPath, 'utf8'); target.set(name, content); target.set(name.replace(/\.(hbs|ejs)$/i, ''), content); }
    }
  }
  await readDirectory(directory, result.templates); await readDirectory(path.join(directory, 'partials'), result.partials); await readDirectory(path.join(directory, 'layouts'), result.layouts); return result;
}
function templateName(value: unknown, fallback: string): string { return typeof value === 'string' && value.trim() ? value.trim() : fallback; }
function defaultPage(page: Page): string { return `<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n<title>${escapeHtml(page.title)}</title>\n</head>\n<body>\n<main>\n<h1>${escapeHtml(page.title)}</h1>\n${page.date ? `<time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>\n` : ''}${page.tags.length ? `<p class="tags">${page.tags.map((tag) => `<span>${escapeHtml(tag)}</span>`).join(' ')}</p>\n` : ''}${page.html}\n</main>\n</body>\n</html>\n`; }
function defaultIndex(pages: Page[]): string { const items = pages.map((page) => `<li><a href="${escapeHtml(page.outputPath)}">${escapeHtml(page.title)}</a>${page.date ? ` <time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : ''}</li>`).join('\n'); return `<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n<title>Index</title>\n</head>\n<body>\n<main>\n<h1>Index</h1>\n<ul>\n${items}\n</ul>\n</main>\n</body>\n</html>\n`; }

export class TemplatePlugin implements Plugin {
  private loaded?: LoadedTemplates;
  async onStart(context: BuildContext): Promise<void> { this.loaded = await loadTemplates(context.templatesDir); }
  async onFile(page: Page, context: BuildContext): Promise<void> {
    const loaded = this.loaded!; const data = page.frontmatter ?? {}; const selected = templateName(data.template, 'default');
    const template = loaded.templates.get(selected) ?? loaded.templates.get(`${selected}.hbs`) ?? loaded.templates.get(`${selected}.ejs`);
    const templateContext = { ...data, ...page, content: page.html, body: page.html, page };
    let rendered = template ? renderTemplate(template, templateContext, loaded.partials) : defaultPage(page);
    const layoutName = template ? templateName(data.layout, 'default') : '';
    const layout = layoutName ? loaded.layouts.get(layoutName) ?? loaded.layouts.get(`${layoutName}.hbs`) ?? loaded.layouts.get(`${layoutName}.ejs`) : undefined;
    if (layout) rendered = renderTemplate(layout, { ...templateContext, body: rendered }, loaded.partials);
    await fs.mkdir(path.dirname(path.join(context.outputDir, page.outputPath)), { recursive: true });
    await fs.writeFile(path.join(context.outputDir, page.outputPath), rendered, 'utf8');
  }
  async afterBuild(context: BuildContext): Promise<void> {
    const loaded = this.loaded!; const source = loaded.templates.get('index') ?? loaded.templates.get('index.hbs') ?? loaded.templates.get('index.ejs');
    await fs.writeFile(path.join(context.outputDir, 'index.html'), source ? renderTemplate(source, { pages: context.pages, title: 'Index' }, loaded.partials) : defaultIndex(context.pages), 'utf8');
  }
}
