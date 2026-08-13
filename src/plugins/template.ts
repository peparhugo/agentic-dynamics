import { promises as fs } from 'node:fs';
import path from 'node:path';
import Handlebars from 'handlebars';
import type { BuildContext, BuildPage, Page, Plugin } from '../plugin.js';

function escapeHtml(value: string): string {
  return value.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;').replaceAll("'", '&#39;');
}

async function isFile(filePath: string): Promise<boolean> {
  try {
    return (await fs.stat(filePath)).isFile();
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return false;
    throw error;
  }
}

function templatePath(directory: string, name: string): string {
  const resolved = path.resolve(directory, path.extname(name) ? name : `${name}.hbs`);
  const relative = path.relative(directory, resolved);
  if (relative === '..' || relative.startsWith(`..${path.sep}`) || path.isAbsolute(relative)) {
    throw new Error(`Template must be inside ${directory}: ${name}`);
  }
  return resolved;
}

async function templateFiles(directory: string, base = directory): Promise<string[]> {
  let entries;
  try {
    entries = await fs.readdir(directory, { withFileTypes: true });
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return [];
    throw error;
  }
  return (await Promise.all(entries.map(async (entry) => {
    const absolutePath = path.join(directory, entry.name);
    if (entry.isDirectory()) return templateFiles(absolutePath, base);
    return entry.isFile() && /\.hbs$/i.test(entry.name) ? [path.relative(base, absolutePath)] : [];
  }))).flat();
}

function document(title: string, body: string): string {
  return `<!doctype html>\n<html lang="en">\n<head>\n  <meta charset="utf-8">\n  <meta name="viewport" content="width=device-width, initial-scale=1">\n  <title>${escapeHtml(title)}</title>\n</head>\n<body>\n${body}\n</body>\n</html>\n`;
}

function pageDocument(page: BuildPage): string {
  const date = page.date ? `\n  <time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : '';
  const tags = page.tags.length ? `\n  <ul class="tags">${page.tags.map((tag) => `<li>${escapeHtml(tag)}</li>`).join('')}</ul>` : '';
  return document(page.title, `  <main>\n  <article>\n  <header>\n  <h1>${escapeHtml(page.title)}</h1>${date}${tags}\n  </header>\n  ${page.html}\n  </article>\n  </main>`);
}

function indexDocument(pages: Page[]): string {
  const items = pages.map((page) => {
    const date = page.date ? ` <time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : '';
    return `  <li><a href="${escapeHtml(page.url)}">${escapeHtml(page.title)}</a>${date}</li>`;
  }).join('\n');
  return document('Pages', `  <main>\n  <h1>Pages</h1>\n  <ul>\n${items}\n  </ul>\n  </main>`);
}

export class TemplatePlugin implements Plugin {
  readonly name = 'templates';
  private handlebars = Handlebars.create();
  private defaultTemplate?: string;
  private defaultLayout?: string;

  async beforeBuild(context: BuildContext): Promise<void> {
    const templatesDir = context.options.templatesDir;
    const defaultTemplate = templatePath(templatesDir, 'default');
    const defaultLayout = templatePath(path.join(templatesDir, 'layouts'), 'default');
    const files = await templateFiles(path.join(templatesDir, 'partials'));
    const partials: Record<string, string> = {};
    await Promise.all(files.map(async (file) => {
      const name = file.slice(0, -path.extname(file).length).split(path.sep).join('/');
      partials[name] = await fs.readFile(path.join(templatesDir, 'partials', file), 'utf8');
    }));
    this.handlebars = Handlebars.create();
    this.handlebars.registerPartial(partials);
    this.defaultTemplate = await isFile(defaultTemplate) ? defaultTemplate : undefined;
    this.defaultLayout = await isFile(defaultLayout) ? defaultLayout : undefined;
  }

  async onFile(page: BuildPage, context: BuildContext): Promise<void> {
    const { outputDir, templatesDir } = context.options;
    const destination = path.join(outputDir, page.outputPath);
    const data = { ...page.data, title: page.title, date: page.date, tags: page.tags, sourcePath: page.sourcePath,
      outputPath: page.outputPath, url: page.url, content: page.html, body: page.html };
    const selectedTemplate = page.template ? templatePath(templatesDir, page.template) : this.defaultTemplate;
    let rendered = selectedTemplate
      ? this.handlebars.compile(await fs.readFile(selectedTemplate, 'utf8'))(data)
      : pageDocument(page);
    const selectedLayout = page.layout === false ? undefined : page.layout
      ? templatePath(path.join(templatesDir, 'layouts'), page.layout) : this.defaultLayout;
    if (selectedLayout) {
      rendered = this.handlebars.compile(await fs.readFile(selectedLayout, 'utf8'))({ ...data, body: rendered });
    }
    await fs.mkdir(path.dirname(destination), { recursive: true });
    await fs.writeFile(destination, rendered, 'utf8');
  }

  async afterBuild(context: BuildContext): Promise<void> {
    await fs.writeFile(path.join(context.options.outputDir, 'index.html'), indexDocument(context.pages), 'utf8');
  }
}
