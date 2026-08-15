import { mkdir, readdir, readFile, writeFile } from 'node:fs/promises';
import { join, relative, resolve, sep } from 'node:path';
import Handlebars from 'handlebars';
import type { Plugin } from '../plugin';
import type { Page } from '../site';

type HandlebarsEnvironment = ReturnType<typeof Handlebars.create>;

function escapeHtml(value: string): string {
  return value.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function document(title: string, body: string): string {
  return `<!doctype html>\n<html lang="en">\n<head>\n  <meta charset="utf-8">\n  <meta name="viewport" content="width=device-width, initial-scale=1">\n  <title>${escapeHtml(title)}</title>\n</head>\n<body>\n${body}\n</body>\n</html>\n`;
}

function defaultPage(page: Page): string {
  const metadata = [page.date ? `<time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : '', page.tags.length ? `<p>Tags: ${page.tags.map(escapeHtml).join(', ')}</p>` : ''].filter(Boolean).join('\n');
  return document(page.title, `<main>\n<h1>${escapeHtml(page.title)}</h1>\n${metadata}\n${page.html}\n</main>`);
}

function renderIndex(pages: Page[]): string {
  const links = pages.map((page) => `<li><a href="${encodeURI(page.slug)}.html">${escapeHtml(page.title)}</a></li>`).join('\n');
  return document('Index', `<main>\n<h1>Pages</h1>\n<ul>\n${links}\n</ul>\n</main>`);
}

async function filesIn(directory: string): Promise<string[]> {
  try {
    const entries = await readdir(directory, { withFileTypes: true });
    return (await Promise.all(entries.map(async (entry) => entry.isDirectory() ? filesIn(join(directory, entry.name)) : entry.isFile() ? [join(directory, entry.name)] : []))).flat();
  } catch (error: unknown) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return [];
    throw error;
  }
}

function templatePath(directory: string, name: string): string {
  const path = resolve(directory, name.endsWith('.hbs') ? name : `${name}.hbs`);
  if (relative(directory, path).startsWith('..')) throw new Error(`Template must be inside ${directory}: ${name}`);
  return path;
}

async function readTemplate(directory: string, name: string): Promise<string | undefined> {
  try { return await readFile(templatePath(directory, name), 'utf8'); } catch (error: unknown) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return undefined;
    throw error;
  }
}

async function createTemplates(templateDir: string): Promise<HandlebarsEnvironment> {
  const handlebars = Handlebars.create();
  const partialDir = join(templateDir, 'partials');
  await Promise.all((await filesIn(partialDir)).filter((file) => file.endsWith('.hbs')).map(async (file) => handlebars.registerPartial(relative(partialDir, file).replace(/\.hbs$/, '').split(sep).join('/'), await readFile(file, 'utf8'))));
  return handlebars;
}

async function renderPage(page: Page, templateDir: string, handlebars: HandlebarsEnvironment): Promise<string> {
  const templateName = page.template ?? 'default';
  const pageSource = await readTemplate(templateDir, templateName);
  if (page.template && !pageSource) throw new Error(`Page template not found: ${page.template}`);
  const body = pageSource ? handlebars.compile(pageSource)({ ...page.frontmatter, ...page, content: page.html }) : defaultPage(page);
  const layoutName = page.layout ?? 'default';
  const layoutSource = await readTemplate(join(templateDir, 'layouts'), layoutName);
  if (page.layout && !layoutSource) throw new Error(`Layout template not found: ${page.layout}`);
  return layoutSource ? handlebars.compile(layoutSource)({ ...page.frontmatter, ...page, body }) : document(page.title, body);
}

export class TemplatePlugin implements Plugin {
  private handlebars!: HandlebarsEnvironment;

  async beforeBuild(context: Parameters<NonNullable<Plugin['beforeBuild']>>[0]): Promise<void> {
    this.handlebars = await createTemplates(context.templateDir);
  }

  async onFile(context: Parameters<NonNullable<Plugin['onFile']>>[0]): Promise<void> {
    if (!context.page) return;
    const target = join(context.outputDir, `${context.page.slug}.html`);
    await mkdir(resolve(target, '..'), { recursive: true });
    await writeFile(target, await renderPage(context.page, context.templateDir, this.handlebars), 'utf8');
  }

  async afterBuild(context: Parameters<NonNullable<Plugin['afterBuild']>>[0]): Promise<void> {
    await writeFile(join(context.outputDir, 'index.html'), renderIndex(context.pages), 'utf8');
  }
}
