import { promises as fs } from 'node:fs';
import path from 'node:path';
import Handlebars from 'handlebars';
import { Page } from './types';
import { Plugin, PluginContext } from './plugin';

function fallbackDocument(page: Page): string {
  const escaped = page.frontmatter.title.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c] as string));
  const date = page.frontmatter.date?.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c] as string));
  return `<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n<title>${escaped}</title>\n</head>\n<body>\n<main>\n<h1>${escaped}</h1>\n${date ? `<time datetime="${date}">${date}</time>\n` : ''}${page.html}</main>\n</body>\n</html>\n`;
}

async function templatePath(directory: string, name: string): Promise<string | undefined> {
  const requested = path.extname(name) ? [name] : [`${name}.hbs`, `${name}.handlebars`];
  for (const candidate of requested) {
    try { if ((await fs.stat(path.join(directory, candidate))).isFile()) return path.join(directory, candidate); } catch { /* try next extension */ }
  }
  return undefined;
}

async function registerPartials(handlebars: { registerPartial(name: string, template: string): void }, directory: string, prefix = ''): Promise<void> {
  let entries: import('node:fs').Dirent[];
  try { entries = await fs.readdir(directory, { withFileTypes: true }); } catch { return; }
  for (const entry of entries) {
    const file = path.join(directory, entry.name);
    if (entry.isDirectory()) await registerPartials(handlebars, file, `${prefix}${entry.name}/`);
    else if (entry.isFile() && /\.(hbs|handlebars)$/i.test(entry.name)) handlebars.registerPartial(`${prefix}${entry.name}`.replace(/\.(hbs|handlebars)$/i, ''), await fs.readFile(file, 'utf8'));
  }
}

export class TemplatePlugin implements Plugin {
  async onFile(page: Page, context: PluginContext): Promise<Page> {
    const templateName = page.frontmatter.template || 'default';
    const templateFile = await templatePath(context.templatesDir, templateName);
    if (!templateFile) return { ...page, html: fallbackDocument(page) };
    const handlebars = Handlebars.create();
    await registerPartials(handlebars, path.join(context.templatesDir, 'partials'));
    const values = { ...page.frontmatter, frontmatter: page.frontmatter, page, content: page.html, body: page.html };
    let html = handlebars.compile(await fs.readFile(templateFile, 'utf8'))(values);
    if (page.frontmatter.layout) {
      const layoutFile = await templatePath(path.join(context.templatesDir, 'layouts'), page.frontmatter.layout);
      if (!layoutFile) throw new Error(`Layout template not found: ${page.frontmatter.layout}`);
      html = handlebars.compile(await fs.readFile(layoutFile, 'utf8'))({ ...values, body: html });
    }
    return { ...page, html };
  }
}
