import { promises as fs } from 'node:fs';
import path from 'node:path';
import Handlebars from 'handlebars';
import type { Plugin, PluginContext, PluginPage } from '../plugin';

async function exists(file: string): Promise<boolean> {
  try {
    await fs.access(file);
    return true;
  } catch {
    return false;
  }
}

async function templateFiles(directory: string): Promise<string[]> {
  if (!await exists(directory)) return [];
  const entries = await fs.readdir(directory, { withFileTypes: true });
  const files = await Promise.all(entries.map(async (entry) => {
    const entryPath = path.join(directory, entry.name);
    if (entry.isDirectory()) return templateFiles(entryPath);
    return /\.hbs$/i.test(entry.name) ? [entryPath] : [];
  }));
  return files.flat().sort();
}

function namedTemplate(directory: string, value: unknown, field: string): string | undefined {
  if (typeof value !== 'string' || value.trim() === '') return undefined;
  const name = value.trim().replace(/\.hbs$/i, '') + '.hbs';
  const file = path.resolve(directory, name);
  const relative = path.relative(directory, file);
  if (relative.startsWith(`..${path.sep}`) || path.isAbsolute(relative)) {
    throw new Error(`${field} must be inside ${directory}`);
  }
  return file;
}

function escapeHtml(value: string): string {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function document(title: string, body: string): string {
  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>${escapeHtml(title)}</title>
</head>
<body>
${body}
</body>
</html>
`;
}

function pageDocument(page: PluginPage): string {
  const metadata = [
    page.date ? `<time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : '',
    page.tags.length > 0
      ? `<ul class="tags">${page.tags.map((tag) => `<li>${escapeHtml(tag)}</li>`).join('')}</ul>`
      : ''
  ].filter(Boolean).join('\n');
  return document(page.title, `<article>
  <header>
    <h1>${escapeHtml(page.title)}</h1>
    ${metadata}
  </header>
  ${page.content}
</article>`);
}

export function indexDocument(pages: PluginPage[]): string {
  const items = pages.map((page) => {
    const date = page.date ? ` <time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : '';
    const href = page.outputPath.split(path.sep).map(encodeURIComponent).join('/');
    return `<li><a href="${href}">${escapeHtml(page.title)}</a>${date}</li>`;
  }).join('\n    ');
  return document('Pages', `<main>
  <h1>Pages</h1>
  <ul>
    ${items}
  </ul>
</main>`);
}

export class TemplatePlugin implements Plugin {
  readonly name = 'templates';
  private engine: typeof Handlebars = Handlebars.create() as typeof Handlebars;

  async beforeBuild(context: PluginContext): Promise<void> {
    this.engine = Handlebars.create() as typeof Handlebars;
    const partialsDir = path.join(context.options.templatesDir, 'partials');
    for (const file of await templateFiles(partialsDir)) {
      const name = path.relative(partialsDir, file).replace(/\.hbs$/i, '').split(path.sep).join('/');
      this.engine.registerPartial(name, await fs.readFile(file, 'utf8'));
    }
  }

  async onFile(page: PluginPage, context: PluginContext): Promise<void> {
    const templatesDir = context.options.templatesDir;
    const defaultTemplate = path.join(templatesDir, 'default.hbs');
    const defaultLayout = path.join(templatesDir, 'layouts', 'default.hbs');
    const render = async (file: string, values: Record<string, unknown>): Promise<string> => {
      if (!await exists(file)) throw new Error(`Template not found: ${file}`);
      return this.engine.compile(await fs.readFile(file, 'utf8'))(values);
    };
    const values: Record<string, unknown> = {
      ...page.data,
      title: page.title,
      date: page.date,
      tags: page.tags,
      outputPath: page.outputPath,
      content: page.content,
      body: page.content
    };
    const selectedTemplate = namedTemplate(templatesDir, page.data.template, 'template');
    if (selectedTemplate) page.html = await render(selectedTemplate, values);
    else if (await exists(defaultTemplate)) page.html = await render(defaultTemplate, values);
    else page.html = pageDocument(page);

    const layoutsDir = path.join(templatesDir, 'layouts');
    const selectedLayout = namedTemplate(layoutsDir, page.data.layout, 'layout');
    const layout = selectedLayout ?? (await exists(defaultLayout) ? defaultLayout : undefined);
    if (layout) page.html = await render(layout, { ...values, body: page.html });
  }
}
