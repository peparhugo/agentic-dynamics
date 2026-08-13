import { promises as fs } from 'node:fs';
import path from 'node:path';
import Handlebars from 'handlebars';
import type { BuildContext, Plugin, SourcePage } from './types.js';

function escapeHtml(value: string): string {
  return value.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function document(title: string, body: string): string {
  return `<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n<title>${escapeHtml(title)}</title>\n</head>\n<body>\n${body}\n</body>\n</html>\n`;
}

async function readTemplate(file: string): Promise<string | undefined> {
  try { return await fs.readFile(file, 'utf8'); } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return undefined;
    throw error;
  }
}

export class TemplatePlugin implements Plugin {
  private render?: (page: SourcePage) => Promise<string>;

  async beforeBuild(context: BuildContext): Promise<void> {
    const handlebars = Handlebars.create();
    try {
      const partials = await fs.readdir(path.join(context.templatesDir, 'partials'), { withFileTypes: true });
      await Promise.all(partials.filter((entry) => entry.isFile() && /\.hbs$/i.test(entry.name)).map(async (entry) => handlebars.registerPartial(path.basename(entry.name, '.hbs'), await fs.readFile(path.join(context.templatesDir, 'partials', entry.name), 'utf8'))));
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code !== 'ENOENT') throw error;
    }
    this.render = async (page) => {
      const templateName = page.template ?? 'default';
      const template = await readTemplate(path.join(context.templatesDir, `${templateName}.hbs`));
      if (!template) return document(page.title, `<article>\n<h1>${escapeHtml(page.title)}</h1>\n${page.html}</article>`);
      const body = handlebars.compile(template)({ ...page.metadata, ...page, content: page.html });
      const layout = await readTemplate(path.join(context.templatesDir, 'layouts', `${templateName}.hbs`)) ?? await readTemplate(path.join(context.templatesDir, 'layouts', 'default.hbs'));
      return layout ? handlebars.compile(layout)({ ...page.metadata, ...page, content: page.html, body }) : body;
    };
    await fs.mkdir(context.outputDir, { recursive: true });
  }

  async onFile(page: SourcePage, context: BuildContext): Promise<void> {
    if (!this.render) throw new Error('TemplatePlugin must run before files are rendered');
    await fs.writeFile(path.join(context.outputDir, `${page.slug}.html`), await this.render(page));
  }

  async afterBuild(context: BuildContext): Promise<void> {
    if (!context.shouldBuildIndex) return;
    const links = context.pages.map((page) => {
      const details = [page.date, page.tags.length > 0 ? page.tags.join(', ') : undefined].filter(Boolean).join(' | ');
      return `<li><a href="${encodeURIComponent(page.slug)}.html">${escapeHtml(page.title)}</a>${details ? ` <small>${escapeHtml(details)}</small>` : ''}</li>`;
    }).join('\n');
    await fs.writeFile(path.join(context.outputDir, 'index.html'), document('Pages', `<main>\n<h1>Pages</h1>\n<ul>\n${links}\n</ul>\n</main>`));
  }
}
