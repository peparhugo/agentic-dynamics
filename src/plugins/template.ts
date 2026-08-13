import { mkdir, readdir, readFile, writeFile } from 'node:fs/promises';
import { dirname, extname, join, relative } from 'node:path';
import Handlebars from 'handlebars';
import type { Page } from '../generator.js';
import type { BuildContext, Plugin } from '../plugin.js';

function escapeHtml(value: string): string {
  return value.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function layout(title: string, body: string): string {
  return `<!doctype html>\n<html lang="en">\n<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>${escapeHtml(title)}</title></head>\n<body>\n${body}\n</body>\n</html>\n`;
}

function defaultPage(page: Page): string {
  const details = [page.date ? `<time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : '', page.tags.length ? `<p>Tags: ${page.tags.map(escapeHtml).join(', ')}</p>` : ''].filter(Boolean).join('\n');
  return layout(page.title, `<article>\n<h1>${escapeHtml(page.title)}</h1>\n${details}\n${page.html}</article>`);
}

function indexHtml(pages: Page[]): string {
  const items = pages.map((page) => `<li><a href="${encodeURI(`${page.slug}.html`)}">${escapeHtml(page.title)}</a>${page.date ? ` <time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : ''}</li>`).join('\n');
  return layout('Index', `<main>\n<h1>Pages</h1>\n<ul>\n${items}\n</ul>\n</main>`);
}

async function templateFiles(directory: string): Promise<string[]> {
  try {
    const entries = await readdir(directory, { withFileTypes: true });
    const files = await Promise.all(entries.map(async (entry) => {
      const file = join(directory, entry.name);
      if (entry.isDirectory()) return templateFiles(file);
      return extname(entry.name).toLowerCase() === '.hbs' ? [file] : [];
    }));
    return files.flat();
  } catch (error: unknown) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return [];
    throw error;
  }
}

export class TemplatePlugin implements Plugin {
  private templates: Map<string, Handlebars.TemplateDelegate> | undefined;

  async beforeBuild(context: BuildContext): Promise<void> {
    const files = await templateFiles(context.options.templatesDir);
    if (files.length === 0) return;
    this.templates = new Map();
    await Promise.all(files.map(async (file) => {
      const name = relative(context.options.templatesDir, file).replace(/\\/g, '/').replace(/\.hbs$/i, '');
      const template = Handlebars.compile(await readFile(file, 'utf8'));
      if (name.startsWith('partials/')) Handlebars.registerPartial(name.slice('partials/'.length), template);
      else this.templates?.set(name, template);
    }));
  }

  async onFile(page: Page, context: BuildContext): Promise<void> {
    let html = defaultPage(page);
    if (this.templates) {
      const templateName = page.template ?? 'page';
      const template = this.templates.get(templateName);
      if (!template) throw new Error(`Template not found: ${templateName}`);
      const body = template({ ...page, content: new Handlebars.SafeString(page.html) });
      const layoutName = `layouts/${page.layout ?? 'default'}`;
      const layoutTemplate = this.templates.get(layoutName);
      if (!layoutTemplate) throw new Error(`Layout not found: ${page.layout ?? 'default'}`);
      html = layoutTemplate({ ...page, body: new Handlebars.SafeString(body) });
    }
    const destination = join(context.options.outputDir, `${page.slug}.html`);
    await mkdir(dirname(destination), { recursive: true });
    await writeFile(destination, html);
  }

  async afterBuild(context: BuildContext): Promise<void> {
    await writeFile(join(context.options.outputDir, 'index.html'), indexHtml(context.pages));
  }
}
