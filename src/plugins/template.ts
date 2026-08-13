import { promises as fs } from 'node:fs';
import path from 'node:path';
import Handlebars from 'handlebars';
import type { BuildContext, Page, Plugin } from '../types';

const escapeHtml = (value: string): string => value.replace(/[&<>'"]/g, (character) => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;',
}[character] as string));

const renderLayout = (title: string, content: string): string => `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>${escapeHtml(title)}</title>
</head>
<body>
${content}
</body>
</html>
`;

export function renderPage(page: Page): string {
  const date = page.date ? `\n  <time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : '';
  const tags = page.tags.length
    ? `\n  <ul class="tags">${page.tags.map((tag) => `<li>${escapeHtml(tag)}</li>`).join('')}</ul>`
    : '';
  return renderLayout(page.title, `  <main>\n  <article>\n  <header>\n  <h1>${escapeHtml(page.title)}</h1>${date}${tags}\n  </header>\n${page.html}  </article>\n  </main>`);
}

export function renderIndex(pages: Page[]): string {
  const items = pages.map((page) => {
    const date = page.date ? ` <time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : '';
    return `    <li><a href="${escapeHtml(page.url)}">${escapeHtml(page.title)}</a>${date}</li>`;
  }).join('\n');
  const list = items ? `\n  <ul>\n${items}\n  </ul>` : '\n  <p>No pages found.</p>';
  return renderLayout('Pages', `  <main>\n  <h1>Pages</h1>${list}\n  </main>`);
}

const templateName = (name: string): string => name.toLowerCase().endsWith('.hbs') ? name : `${name}.hbs`;

const safeTemplatePath = (directory: string, name: string): string => {
  const resolvedDirectory = path.resolve(directory);
  const resolved = path.resolve(directory, templateName(name));
  const relative = path.relative(resolvedDirectory, resolved);
  if (relative.startsWith('..') || path.isAbsolute(relative)) throw new Error(`Template path must stay within ${resolvedDirectory}: ${name}`);
  return resolved;
};

const readNamedTemplate = async (directory: string, name: string, kind: string): Promise<string> => {
  const filename = safeTemplatePath(directory, name);
  return fs.readFile(filename, 'utf8').catch((error: unknown) => {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') throw new Error(`${kind} not found: ${name}`);
    throw error;
  });
};

export class TemplatePlugin implements Plugin {
  readonly name = 'templates';
  private handlebars = Handlebars.create();
  private useTemplates = false;

  async beforeBuild(context: BuildContext): Promise<void> {
    this.handlebars = Handlebars.create();
    const stats = await fs.stat(context.templateDir).catch(() => undefined);
    this.useTemplates = stats?.isDirectory() ?? false;
    if (this.useTemplates) await this.loadPartials(path.join(context.templateDir, 'partials'));
    await fs.rm(context.outputDir, { recursive: true, force: true });
    await fs.mkdir(context.outputDir, { recursive: true });
  }

  async onFile(page: Page, context: BuildContext): Promise<void> {
    const destination = path.join(context.outputDir, page.outputPath);
    await fs.mkdir(path.dirname(destination), { recursive: true });
    await fs.writeFile(destination, this.useTemplates ? await this.renderTemplatedPage(page, context.templateDir) : renderPage(page), 'utf8');
  }

  async afterBuild(context: BuildContext): Promise<void> {
    await fs.writeFile(path.join(context.outputDir, 'index.html'), renderIndex(context.pages), 'utf8');
  }

  private async loadPartials(partialsDir: string): Promise<void> {
    const entries = await fs.readdir(partialsDir, { withFileTypes: true }).catch((error: unknown) => {
      if ((error as NodeJS.ErrnoException).code === 'ENOENT') return [];
      throw error;
    });
    await Promise.all(entries.map(async (entry) => {
      if (!entry.isFile() || !entry.name.toLowerCase().endsWith('.hbs')) return;
      const source = await fs.readFile(path.join(partialsDir, entry.name), 'utf8');
      this.handlebars.registerPartial(path.basename(entry.name, path.extname(entry.name)), source);
    }));
  }

  private async renderTemplatedPage(page: Page, templatesDir: string): Promise<string> {
    const template = await readNamedTemplate(templatesDir, page.template ?? 'default', 'Template');
    const context = { ...page.data, ...page, content: page.html };
    const content = this.handlebars.compile(template)(context);
    const layout = await readNamedTemplate(path.join(templatesDir, 'layouts'), page.layout ?? 'default', 'Layout');
    return this.handlebars.compile(layout)({ ...context, body: content });
  }
}
