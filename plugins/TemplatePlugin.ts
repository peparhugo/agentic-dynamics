import { existsSync, mkdirSync, readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { extname, join, relative } from 'node:path';
import Handlebars from 'handlebars';
import type { Page } from '../src/generator';
import type { Plugin } from '../src/plugin';

function escapeHtml(value: string): string {
  return value.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function document(title: string, body: string): string {
  return `<!doctype html>\n<html lang="en">\n<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>${escapeHtml(title)}</title></head>\n<body>\n${body}\n</body>\n</html>\n`;
}

function renderPage(page: Page): string {
  const metadata = [page.date, page.tags.length ? page.tags.join(', ') : undefined].filter(Boolean).join(' | ');
  return document(page.title, `<article>\n<h1>${escapeHtml(page.title)}</h1>${metadata ? `\n<p>${escapeHtml(metadata)}</p>` : ''}\n${page.html}</article>`);
}

function hbsFile(directory: string, name: string): string {
  return join(directory, name.endsWith('.hbs') ? name : `${name}.hbs`);
}

function hbsFiles(directory: string): string[] {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) return hbsFiles(path);
    return entry.isFile() && extname(entry.name).toLowerCase() === '.hbs' ? [path] : [];
  });
}

function renderTemplate(path: string, context: Page & { body?: string; content?: string }): string {
  return Handlebars.compile(readFileSync(path, 'utf8'))(context);
}

function renderTemplatedPage(page: Page, templatesDir: string): string {
  const templatePath = hbsFile(templatesDir, page.template ?? 'default');
  if (!existsSync(templatePath)) {
    if (!page.template) return renderPage(page);
    throw new Error(`Template does not exist: ${templatePath}`);
  }
  const body = renderTemplate(templatePath, { ...page, content: page.html });
  const layoutPath = hbsFile(join(templatesDir, 'layouts'), page.layout ?? 'default');
  if (!existsSync(layoutPath)) {
    if (!page.layout) return body;
    throw new Error(`Layout does not exist: ${layoutPath}`);
  }
  return renderTemplate(layoutPath, { ...page, body, content: page.html });
}

export const TemplatePlugin: Plugin = {
  beforeBuild({ options }) {
    Handlebars.partials = {};
    const partialsDir = join(options.templatesDir, 'partials');
    if (!existsSync(partialsDir)) return;
    for (const path of hbsFiles(partialsDir)) {
      Handlebars.registerPartial(relative(partialsDir, path).replace(/\\/g, '/').replace(/\.hbs$/i, ''), readFileSync(path, 'utf8'));
    }
  },
  onFile(page, context) {
    if (!context.file) return;
    if (context.file.cacheHit) return;
    mkdirSync(join(context.file.outputPath, '..'), { recursive: true });
    writeFileSync(context.file.outputPath, renderTemplatedPage(page, context.options.templatesDir));
  },
  afterBuild(context) {
    const links = context.pages.map((page) => `<li><a href="${escapeHtml(`${page.slug}.html`)}">${escapeHtml(page.title)}</a>${page.date ? ` <time>${escapeHtml(page.date)}</time>` : ''}</li>`).join('\n');
    writeFileSync(join(context.options.outputDir, 'index.html'), document('Index', `<main>\n<h1>Pages</h1>\n<ul>\n${links}\n</ul>\n</main>`));
  },
};
