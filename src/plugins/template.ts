import { readdir, readFile, stat, writeFile } from 'node:fs/promises';
import { join, relative } from 'node:path';
import Handlebars from 'handlebars';
import { Page } from '../generator';
import { Plugin } from '../plugin';

function escapeHtml(value: string): string {
  return value.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function defaultPageBody(page: Page): string {
  return `<article>\n<h1>${escapeHtml(page.title)}</h1>${page.date ? `\n<time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : ''}${page.tags.length ? `\n<p>Tags: ${page.tags.map(escapeHtml).join(', ')}</p>` : ''}\n${page.html}\n</article>`;
}

function defaultPage(page: Page): string {
  return `<!doctype html>\n<html lang="en">\n<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>${escapeHtml(page.title)}</title></head>\n<body>\n${defaultPageBody(page)}\n</body>\n</html>\n`;
}

async function fileIfExists(path: string): Promise<string | undefined> {
  try { return (await stat(path)).isFile() ? readFile(path, 'utf8') : undefined; } catch (error: unknown) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return undefined;
    throw error;
  }
}

async function templateFiles(directory: string): Promise<string[]> {
  try {
    const entries = await readdir(directory, { withFileTypes: true });
    return (await Promise.all(entries.map((entry) => {
      const path = join(directory, entry.name);
      return entry.isDirectory() ? templateFiles(path) : entry.isFile() && /\.hbs$/i.test(entry.name) ? Promise.resolve([path]) : Promise.resolve([]);
    }))).flat();
  } catch (error: unknown) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return [];
    throw error;
  }
}

function templatePath(directory: string, name: string): string {
  if (!/^[\w./-]+$/.test(name) || name.split('/').includes('..')) throw new Error(`Invalid template name: ${name}`);
  return join(directory, name.endsWith('.hbs') ? name : `${name}.hbs`);
}

async function renderPage(page: Page, templateDir: string): Promise<string> {
  const partialDir = join(templateDir, 'partials');
  const renderer = Handlebars.create();
  await Promise.all((await templateFiles(partialDir)).map(async (path) => renderer.registerPartial(relative(partialDir, path).replace(/\\/g, '/').replace(/\.hbs$/i, ''), await readFile(path, 'utf8'))));
  const template = await fileIfExists(templatePath(templateDir, page.template ?? 'default'));
  if (!template && page.template) throw new Error(`Template not found: ${page.template}`);
  const context = { ...page, body: defaultPageBody(page) };
  const body = template ? renderer.compile(template)(context) : defaultPageBody(page);
  const layout = await fileIfExists(templatePath(join(templateDir, 'layouts'), page.layout ?? 'default'));
  if (!layout && page.layout) throw new Error(`Layout not found: ${page.layout}`);
  return layout ? renderer.compile(layout)({ ...context, body }) : template ? body : defaultPage(page);
}

function renderIndex(pages: Page[]): string {
  const items = pages.map((page) => `<li><a href="${escapeHtml(`${page.slug}.html`)}">${escapeHtml(page.title)}</a>${page.date ? ` <time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : ''}</li>`).join('\n');
  return `<!doctype html>\n<html lang="en">\n<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Pages</title></head>\n<body>\n<h1>Pages</h1>\n<ul>\n${items}\n</ul>\n</body>\n</html>\n`;
}

export const TemplatePlugin: Plugin = {
  async onFile(page, context) { context.renderedPages.set(page.outputPath, await renderPage(page, context.templateDir)); },
  async afterBuild(context) { await writeFile(join(context.outputDir, 'index.html'), renderIndex(context.pages), 'utf8'); },
};
