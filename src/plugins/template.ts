import { mkdir, readdir, readFile, rm, stat, writeFile } from 'node:fs/promises';
import path from 'node:path';
import Handlebars from 'handlebars';
import type { Page } from '../generator.js';
import type { BuildContext, Plugin } from '../plugin.js';

function escapeHtml(value: string): string {
  return value.replace(/[&<>"']/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[character] ?? character);
}

async function directoryExists(directory: string): Promise<boolean> {
  try { return (await stat(directory)).isDirectory(); } catch (error: unknown) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return false;
    throw error;
  }
}

async function renderTemplate(templatesDir: string, name: string, context: object): Promise<string> {
  try {
    return Handlebars.compile(await readFile(path.join(templatesDir, `${name}.hbs`), 'utf8'))(context);
  } catch (error: unknown) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') throw new Error(`Template not found: ${name}`);
    throw error;
  }
}

function pageDocument(page: Page): string {
  const date = page.date ? `<time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : '';
  const tags = page.tags.length ? `<ul class="tags">${page.tags.map((tag) => `<li>${escapeHtml(tag)}</li>`).join('')}</ul>` : '';
  return `<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>${escapeHtml(page.title)}</title></head>
<body><main><nav><a href="index.html">Home</a></nav><article><h1>${escapeHtml(page.title)}</h1>${date}${tags}${page.html}</article></main></body>
</html>`;
}

function indexDocument(pages: Page[]): string {
  const items = pages.map((page) => `<li><a href="${encodeURIComponent(page.slug)}.html">${escapeHtml(page.title)}</a>${page.date ? ` <time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : ''}</li>`).join('');
  return `<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Pages</title></head>
<body><main><h1>Pages</h1><ul>${items}</ul></main></body>
</html>`;
}

export class TemplatePlugin implements Plugin {
  private hasTemplates = false;

  async onStart(context: BuildContext): Promise<void> {
    this.hasTemplates = await directoryExists(context.options.templatesDir);
    if (this.hasTemplates) {
      const partialsDir = path.join(context.options.templatesDir, 'partials');
      if (await directoryExists(partialsDir)) {
        const entries = await readdir(partialsDir, { withFileTypes: true });
        await Promise.all(entries.filter((entry) => entry.isFile() && /\.hbs$/i.test(entry.name)).map(async (entry) => {
          Handlebars.registerPartial(entry.name.replace(/\.hbs$/i, ''), await readFile(path.join(partialsDir, entry.name), 'utf8'));
        }));
      }
    }
    await rm(context.options.outputDir, { recursive: true, force: true });
    await mkdir(context.options.outputDir, { recursive: true });
  }

  async onFile(page: Page, context: BuildContext): Promise<void> {
    const html = this.hasTemplates
      ? await this.renderWithTemplates(page, context.options.templatesDir)
      : pageDocument(page);
    await writeFile(path.join(context.options.outputDir, `${page.slug}.html`), html);
  }

  async afterBuild(context: BuildContext): Promise<void> {
    await writeFile(path.join(context.options.outputDir, 'index.html'), indexDocument(context.pages));
  }

  private async renderWithTemplates(page: Page, templatesDir: string): Promise<string> {
    const context = { ...page.data, ...page };
    const content = await renderTemplate(templatesDir, page.template ?? 'default', context);
    return renderTemplate(path.join(templatesDir, 'layouts'), page.layout ?? 'default', { ...context, body: new Handlebars.SafeString(content) });
  }
}
