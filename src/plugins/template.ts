import { existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join, relative, sep } from 'node:path';
import Handlebars from 'handlebars';
import type { Page } from '../site';
import type { BuildContext, Plugin } from './plugin';

const escapeHtml = (value: string): string => value.replace(/[&<>"']/g, (character) => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
})[character] ?? character);

function templateFiles(directory: string): string[] {
  if (!existsSync(directory)) return [];
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) return templateFiles(path);
    return entry.isFile() && /\.hbs$/i.test(entry.name) ? [path] : [];
  });
}

function templateName(path: string, directory: string): string {
  return relative(directory, path).replace(/\\/g, '/').replace(/\.hbs$/i, '');
}

function renderArticle(page: Page): string {
  const metadata = [
    page.date ? `<time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : '',
    page.tags.length > 0 ? `<p class="tags">${page.tags.map((tag) => `<span>${escapeHtml(tag)}</span>`).join(' ')}</p>` : ''
  ].filter(Boolean).join('\n');
  return `<article>\n  <h1>${escapeHtml(page.title)}</h1>\n  ${metadata}\n  ${page.html}\n</article>`;
}

function renderPage(page: Page): string {
  return `<!doctype html>\n<html lang="en">\n<head>\n  <meta charset="utf-8">\n  <meta name="viewport" content="width=device-width, initial-scale=1">\n  <title>${escapeHtml(page.title)}</title>\n</head>\n<body>\n  <main>\n    ${renderArticle(page)}\n  </main>\n</body>\n</html>\n`;
}

export function renderIndex(pages: Page[]): string {
  const links = pages.map((page) => `      <li><a href="${escapeHtml(page.url)}">${escapeHtml(page.title)}</a>${page.date ? ` <time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : ''}</li>`).join('\n');
  return `<!doctype html>\n<html lang="en">\n<head>\n  <meta charset="utf-8">\n  <meta name="viewport" content="width=device-width, initial-scale=1">\n  <title>Pages</title>\n</head>\n<body>\n  <main>\n    <h1>Pages</h1>\n    <ul>\n${links}\n    </ul>\n  </main>\n</body>\n</html>\n`;
}

export class TemplatePlugin implements Plugin {
  private render?: (page: Page) => string;

  beforeBuild(context: BuildContext): void {
    const handlebars = Handlebars.create();
    const partialsDir = join(context.templatesDir, 'partials');
    for (const file of templateFiles(partialsDir)) handlebars.registerPartial(templateName(file, partialsDir), readFileSync(file, 'utf8'));
    const templates = new Map<string, Handlebars.TemplateDelegate>();
    for (const file of templateFiles(context.templatesDir)) {
      const root = relative(context.templatesDir, file).split(sep)[0];
      if (root !== 'layouts' && root !== 'partials') templates.set(templateName(file, context.templatesDir), handlebars.compile(readFileSync(file, 'utf8')));
    }
    const layoutsDir = join(context.templatesDir, 'layouts');
    const layouts = new Map<string, Handlebars.TemplateDelegate>();
    for (const file of templateFiles(layoutsDir)) layouts.set(templateName(file, layoutsDir), handlebars.compile(readFileSync(file, 'utf8')));
    this.render = (page) => {
      const template = templates.get(page.template ?? 'default');
      if (page.template && !template) throw new Error(`Template does not exist: ${page.template}`);
      const body = template ? template({ ...page, content: page.html }) : renderArticle(page);
      const layoutName = page.layout ?? (layouts.has('default') ? 'default' : undefined);
      if (!layoutName) return template ? body : renderPage(page);
      const layout = layouts.get(layoutName);
      if (!layout) throw new Error(`Layout does not exist: ${layoutName}`);
      return layout({ ...page, content: page.html, body });
    };
  }

  onFile(page: Page): void {
    if (!this.render) throw new Error('Template plugin was not initialized');
    mkdirSync(dirname(page.outputPath), { recursive: true });
    writeFileSync(page.outputPath, this.render(page), 'utf8');
  }

  afterBuild(context: BuildContext): void {
    writeFileSync(join(context.outputDir, 'index.html'), renderIndex(context.pages), 'utf8');
  }
}
