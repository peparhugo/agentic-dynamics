import { promises as fs } from 'node:fs';
import path from 'node:path';
import type { Page } from './generator';
import type { Plugin, PluginContext } from './plugin';

function escapeHtml(value: string): string {
  return value.replace(/[&<>'"]/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[character] ?? character));
}

async function existingFile(directory: string, name: string, extensions: string[]): Promise<string | undefined> {
  const candidates = path.extname(name) ? [name] : extensions.map((extension) => `${name}${extension}`);
  for (const candidate of candidates) {
    try { const file = path.join(directory, candidate); if ((await fs.stat(file)).isFile()) return file; } catch { /* optional template */ }
  }
  return undefined;
}

function value(context: Record<string, unknown>, name: string): unknown {
  if (name === 'this' || name === '.') return context;
  if (name.startsWith('this.')) return value(context, name.slice(5));
  return name.split('.').reduce<unknown>((current, key) => current && typeof current === 'object' ? (current as Record<string, unknown>)[key] : undefined, context);
}

function render(source: string, context: Record<string, unknown>, partials: Record<string, string>): string {
  const blocks = source.replace(/{{#each\s+([\w.$-]+)}}([\s\S]*?){{\/each}}/g, (_m, name: string, block: string) => {
    const items = value(context, name);
    return Array.isArray(items) ? items.map((item) => render(block, (item && typeof item === 'object' ? item : { this: item }) as Record<string, unknown>, partials)).join('') : '';
  });
  const expanded = blocks.replace(/{{>\s*([\w./-]+)(?:\s+[^}]*)?}}/g, (_m, name: string) => {
    const partial = partials[name] ?? partials[name.replace(/\.(?:hbs|handlebars|ejs)$/i, '')];
    return partial ? render(partial, context, partials) : '';
  });
  return expanded.replace(/{{{\s*([\w.$-]+)\s*}}}/g, (_m, name: string) => String(value(context, name) ?? ''))
    .replace(/{{\s*([\w.$-]+)\s*}}/g, (_m, name: string) => escapeHtml(String(value(context, name) ?? '')));
}

async function loadPartials(directory: string): Promise<Record<string, string>> {
  const result: Record<string, string> = {};
  try {
    for (const entry of await fs.readdir(directory, { withFileTypes: true })) {
      if (entry.isFile() && /\.(hbs|handlebars|ejs)$/i.test(entry.name)) result[entry.name.replace(/\.(hbs|handlebars|ejs)$/i, '')] = await fs.readFile(path.join(directory, entry.name), 'utf8');
    }
  } catch { /* optional partials directory */ }
  return result;
}

function document(title: string, body: string): string { return `<!doctype html>\n<html lang="en">\n<head>\n  <meta charset="utf-8">\n  <meta name="viewport" content="width=device-width, initial-scale=1">\n  <title>${escapeHtml(title)}</title>\n</head>\n<body>\n${body}\n</body>\n</html>\n`; }

export class TemplatePlugin implements Plugin {
  private partials: Record<string, string> = {};
  async onStart(context: PluginContext): Promise<void> { this.partials = await loadPartials(path.join(context.templatesDir, 'partials')); }

  async onFile(page: Page, context: PluginContext): Promise<Page> {
    const template = await existingFile(context.templatesDir, page.template ?? 'default', ['.hbs', '.handlebars', '.ejs']);
    const selectedLayout = page.layout ?? (template ? 'default' : undefined);
    const layoutFile = selectedLayout ? await existingFile(path.join(context.templatesDir, 'layouts'), selectedLayout, ['.hbs', '.handlebars', '.ejs']) : undefined;
    const data = page as Page & { body?: string; content?: string };
    const values = { ...(data as unknown as Record<string, unknown>), title: page.title, content: data.content, body: data.body };
    const pageBody = template ? render(await fs.readFile(template, 'utf8'), values, this.partials) : data.body ?? '';
    const html = layoutFile ? render(await fs.readFile(layoutFile, 'utf8'), { ...values, body: pageBody }, this.partials) : document(page.title, pageBody);
    return Object.assign(page, { layout: selectedLayout, html });
  }

  async afterBuild(context: PluginContext): Promise<void> {
    const links = context.pages.map((page) => `    <li><a href="${page.output.split(path.sep).join('/')}">${escapeHtml(page.title)}</a>${page.date ? ` <time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : ''}</li>`).join('\n');
    const indexBody = `<main>\n  <h1>Pages</h1>\n  <ul>\n${links}\n  </ul>\n</main>`;
    const template = await existingFile(context.templatesDir, 'index', ['.hbs', '.handlebars', '.ejs']);
    const layout = await existingFile(path.join(context.templatesDir, 'layouts'), 'default', ['.hbs', '.handlebars', '.ejs']);
    const values = { title: 'Pages', pages: context.pages, content: indexBody, body: indexBody };
    const body = template ? render(await fs.readFile(template, 'utf8'), values, this.partials) : indexBody;
    await fs.writeFile(path.join(context.outputDir, 'index.html'), layout ? render(await fs.readFile(layout, 'utf8'), { ...values, body }, this.partials) : document('Pages', body), 'utf8');
  }
}
