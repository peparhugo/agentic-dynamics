import { promises as fs } from 'node:fs';
import path from 'node:path';
import Handlebars from 'handlebars';
import type { Plugin, PluginPage } from '../plugin';

export function escapeHtml(value: string): string {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

export function renderDocument(title: string, body: string): string {
  const safeTitle = escapeHtml(title);
  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>${safeTitle}</title>
</head>
<body>
  <main>
    <h1>${safeTitle}</h1>
${body}
  </main>
</body>
</html>
`;
}

function isWithin(parent: string, candidate: string): boolean {
  const relative = path.relative(parent, candidate);
  return relative === '' || (!relative.startsWith(`..${path.sep}`) && relative !== '..' && !path.isAbsolute(relative));
}

async function isFile(file: string): Promise<boolean> {
  try {
    return (await fs.stat(file)).isFile();
  } catch (error: unknown) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return false;
    throw error;
  }
}

function templatePath(directory: string, value: string): string {
  const name = value.endsWith('.hbs') ? value : `${value}.hbs`;
  const resolved = path.resolve(directory, name);
  if (!isWithin(directory, resolved) || path.extname(resolved).toLowerCase() !== '.hbs') {
    throw new Error(`Invalid template path: ${value}`);
  }
  return resolved;
}

async function registerPartials(handlebars: typeof Handlebars, directory: string, root = directory): Promise<void> {
  let entries;
  try {
    entries = await fs.readdir(directory, { withFileTypes: true });
  } catch (error: unknown) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return;
    throw error;
  }
  await Promise.all(entries.map(async (entry) => {
    const entryPath = path.join(directory, entry.name);
    if (entry.isDirectory()) return registerPartials(handlebars, entryPath, root);
    if (entry.isFile() && path.extname(entry.name).toLowerCase() === '.hbs') {
      const name = path.relative(root, entryPath).slice(0, -4).split(path.sep).join('/');
      handlebars.registerPartial(name, await fs.readFile(entryPath, 'utf8'));
    }
  }));
}

export class TemplatePlugin implements Plugin {
  readonly name = 'templates';
  private handlebars = Handlebars.create();

  constructor(private readonly templatesDir: string) {}

  async onStart(): Promise<void> {
    this.handlebars = Handlebars.create();
    await registerPartials(this.handlebars, path.join(this.templatesDir, 'partials'));
  }

  async onFile(page: PluginPage): Promise<void> {
    const layoutsDir = path.join(this.templatesDir, 'layouts');
    const render = async (directory: string, name: string, context: Record<string, unknown>): Promise<string> => {
      const file = templatePath(directory, name);
      if (!await isFile(file)) throw new Error(`Template not found: ${name}`);
      return this.handlebars.compile(await fs.readFile(file, 'utf8'))(context);
    };
    const metadata = [
      page.date ? `    <time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : '',
      page.tags.length > 0 ? `    <p>Tags: ${page.tags.map(escapeHtml).join(', ')}</p>` : '',
    ].filter(Boolean).join('\n');
    const body = `${metadata}${metadata ? '\n' : ''}    <article>\n${page.content}\n    </article>`;
    const fallback = renderDocument(page.title, body);
    const context: Record<string, unknown> = {
      ...page.data,
      title: page.title,
      date: page.date,
      tags: page.tags,
      url: page.url,
      content: page.content,
    };

    const template = page.data.template;
    const defaultTemplate = await isFile(path.join(this.templatesDir, 'default.hbs'));
    const templateName = typeof template === 'string' && template.trim() ? template.trim() : undefined;
    if (template !== undefined && !templateName) throw new Error('Frontmatter template must be a non-empty string');
    const renderedPage = templateName
      ? await render(this.templatesDir, templateName, context)
      : defaultTemplate ? await render(this.templatesDir, 'default', context) : fallback;

    const layout = page.data.layout;
    const defaultLayout = await isFile(path.join(layoutsDir, 'default.hbs'));
    const layoutName = typeof layout === 'string' && layout.trim() ? layout.trim() : undefined;
    if (layout !== undefined && layout !== false && !layoutName) {
      throw new Error('Frontmatter layout must be a non-empty string or false');
    }
    page.html = layout === false || (!layoutName && !defaultLayout)
      ? renderedPage
      : await render(layoutsDir, layoutName ?? 'default', { ...context, body: renderedPage });
  }
}
