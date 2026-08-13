import { mkdir, readdir, readFile, rm, writeFile } from 'node:fs/promises';
import path from 'node:path';
import Handlebars from 'handlebars';
import type { Page } from '../generator';
import type { Plugin, PluginContext } from '../plugin';

function escapeHtml(value: string): string {
  return value.replace(/[&<>'"]/g, (character) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;',
  }[character] as string));
}

function pageDocument(page: Page): string {
  return `<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>${escapeHtml(page.title)}</title></head>
<body><main><h1>${escapeHtml(page.title)}</h1>${page.date ? `<time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : ''}${page.tags.length ? `<p>Tags: ${page.tags.map(escapeHtml).join(', ')}</p>` : ''}${page.html}</main></body>
</html>`;
}

function indexDocument(pages: Page[]): string {
  const items = pages.map((page) => `<li><a href="${encodeURIComponent(page.slug)}.html">${escapeHtml(page.title)}</a>${page.date ? ` <time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : ''}</li>`).join('\n');
  return `<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Pages</title></head>
<body><main><h1>Pages</h1><ul>${items}</ul></main></body>
</html>`;
}

async function readTemplate(directory: string, name: string): Promise<string | undefined> {
  try {
    return await readFile(path.join(directory, `${name}.hbs`), 'utf8');
  } catch (error: unknown) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return undefined;
    throw error;
  }
}

export class TemplatePlugin implements Plugin {
  private handlebars = Handlebars.create();

  async beforeBuild(context: PluginContext): Promise<void> {
    this.handlebars = Handlebars.create();
    const partialsDir = path.join(context.templatesDir, 'partials');
    try {
      const entries = await readdir(partialsDir, { withFileTypes: true });
      await Promise.all(entries.filter((entry) => entry.isFile() && /\.hbs$/i.test(entry.name)).map(async (entry) => {
        this.handlebars.registerPartial(path.basename(entry.name, '.hbs'), await readFile(path.join(partialsDir, entry.name), 'utf8'));
      }));
    } catch (error: unknown) {
      if ((error as NodeJS.ErrnoException).code !== 'ENOENT') throw error;
    }
    await rm(context.outputDir, { recursive: true, force: true });
    await mkdir(context.outputDir, { recursive: true });
  }

  async onFile(page: Page, context: PluginContext): Promise<void> {
    const view = { ...page.data, ...page, body: page.html };
    const source = await readTemplate(context.templatesDir, page.template ?? 'default');
    const body = source ? this.handlebars.compile(source)(view) : pageDocument(page);
    const layoutSource = await readTemplate(path.join(context.templatesDir, 'layouts'), page.layout ?? 'default');
    const html = layoutSource ? this.handlebars.compile(layoutSource)({ ...view, body }) : body;
    await writeFile(path.join(context.outputDir, `${page.slug}.html`), html);
  }

  async afterBuild(context: PluginContext): Promise<void> {
    await writeFile(path.join(context.outputDir, 'index.html'), indexDocument(context.pages));
  }
}
