import { promises as fs } from 'node:fs';
import path from 'node:path';
import Handlebars from 'handlebars';
import type { Plugin, PluginContext } from '../plugin';
import type { Page } from '../types';

type TemplateContext = Record<string, unknown>;

function escapeHtml(value: string): string {
  return value.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;').replaceAll("'", '&#39;');
}

function defaultLayout(title: string, body: string): string {
  return `<!doctype html>\n<html lang="en">\n<head>\n  <meta charset="utf-8">\n  <meta name="viewport" content="width=device-width, initial-scale=1">\n  <title>${escapeHtml(title)}</title>\n</head>\n<body>\n${body}\n</body>\n</html>\n`;
}

function defaultPage(page: Page): string {
  const metadata = [
    page.date ? `<time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : '',
    ...page.tags.map((tag) => `<span class="tag">${escapeHtml(tag)}</span>`),
  ].filter(Boolean).join(' ');
  return `<main>\n  <article>\n    <header><h1>${escapeHtml(page.title)}</h1>${metadata ? `\n    <p>${metadata}</p>` : ''}</header>\n    ${page.html}\n  </article>\n</main>`;
}

function renderIndex(pages: Page[]): string {
  const items = pages.map((page) => {
    const date = page.date ? ` <time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : '';
    return `    <li><a href="${escapeHtml(page.url)}">${escapeHtml(page.title)}</a>${date}</li>`;
  }).join('\n');
  return defaultLayout('Pages', `<main>\n  <h1>Pages</h1>\n  <ul>\n${items}\n  </ul>\n</main>`);
}

async function isFile(file: string): Promise<boolean> {
  try { return (await fs.stat(file)).isFile(); } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return false;
    throw error;
  }
}

function templatePath(directory: string, name: string): string {
  const normalized = name.endsWith('.hbs') ? name : `${name}.hbs`;
  const root = path.resolve(directory);
  const resolved = path.resolve(root, normalized);
  if (resolved !== root && !resolved.startsWith(`${root}${path.sep}`)) {
    throw new Error(`Template path must stay inside ${directory}: ${name}`);
  }
  return resolved;
}

async function templateFiles(directory: string): Promise<string[]> {
  const entries = await fs.readdir(directory, { withFileTypes: true });
  const files = await Promise.all(entries.map(async (entry) => {
    const fullPath = path.join(directory, entry.name);
    if (entry.isDirectory()) return templateFiles(fullPath);
    return /\.hbs$/i.test(entry.name) ? [fullPath] : [];
  }));
  return files.flat().sort();
}

async function loadPartials(directory: string): Promise<Record<string, string>> {
  const partials: Record<string, string> = {};
  let files: string[];
  try { files = await templateFiles(directory); } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return partials;
    throw error;
  }
  await Promise.all(files.map(async (file) => {
    const name = path.relative(directory, file).replace(/\.hbs$/i, '').split(path.sep).join('/');
    partials[name] = await fs.readFile(file, 'utf8');
  }));
  return partials;
}

export class TemplatePlugin implements Plugin {
  readonly name = 'templates';
  private engine = Handlebars.create();

  async beforeBuild(context: PluginContext): Promise<void> {
    this.engine = Handlebars.create();
    this.engine.registerPartial(await loadPartials(path.join(context.options.templates, 'partials')));
  }

  async onFile(page: Page, context: PluginContext): Promise<void> {
    const templateContext: TemplateContext = { ...(page.data ?? {}), ...page, content: page.html };
    const selectedTemplate = page.template ?? 'default';
    const selectedTemplatePath = templatePath(context.options.templates, selectedTemplate);
    const body = await isFile(selectedTemplatePath)
      ? this.engine.compile(await fs.readFile(selectedTemplatePath, 'utf8'))(templateContext)
      : page.template
        ? (() => { throw new Error(`Template not found: ${selectedTemplate}`); })()
        : defaultPage(page);
    const selectedLayout = page.layout ?? 'default';
    const selectedLayoutPath = templatePath(path.join(context.options.templates, 'layouts'), selectedLayout);
    let rendered: string;
    if (await isFile(selectedLayoutPath)) {
      rendered = this.engine.compile(await fs.readFile(selectedLayoutPath, 'utf8'))({ ...templateContext, body });
    } else {
      if (page.layout) throw new Error(`Layout not found: ${selectedLayout}`);
      rendered = defaultLayout(page.title, body);
    }
    const destination = path.join(context.options.output, ...page.url.split('/'));
    await fs.mkdir(path.dirname(destination), { recursive: true });
    await fs.writeFile(destination, rendered, 'utf8');
  }

  async afterBuild(context: PluginContext): Promise<void> {
    await fs.writeFile(path.join(context.options.output, 'index.html'), renderIndex(context.pages), 'utf8');
  }
}
