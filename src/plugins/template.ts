import { promises as fs, type Dirent } from 'node:fs';
import path from 'node:path';
import Handlebars from 'handlebars';
import { renderPage, type Page } from '../index.js';
import type { Plugin } from '../plugin.js';

export const renderedPage = Symbol('renderedPage');
export type RenderedPage = Page & { [renderedPage]?: string };

function templateContext(page: Page): Record<string, unknown> {
  return { ...(page.data ?? {}), title: page.title, date: page.date, tags: page.tags, content: page.html, page };
}

function templatePath(directory: string, name: string): string {
  const fileName = name.toLowerCase().endsWith('.hbs') ? name : `${name}.hbs`;
  const resolved = path.resolve(directory, fileName);
  const relative = path.relative(directory, resolved);
  if (relative === '..' || relative.startsWith(`..${path.sep}`) || path.isAbsolute(relative)) {
    throw new Error(`Template must be inside ${directory}: ${name}`);
  }
  return resolved;
}

async function readOptional(filePath: string): Promise<string | undefined> {
  try {
    return await fs.readFile(filePath, 'utf8');
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return undefined;
    throw error;
  }
}

async function registerPartials(handlebars: typeof Handlebars, directory: string, prefix = ''): Promise<void> {
  let entries: Dirent[];
  try {
    entries = await fs.readdir(directory, { withFileTypes: true });
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return;
    throw error;
  }
  await Promise.all(entries.map(async (entry) => {
    const filePath = path.join(directory, entry.name);
    if (entry.isDirectory()) await registerPartials(handlebars, filePath, `${prefix}${entry.name}/`);
    else if (entry.isFile() && entry.name.toLowerCase().endsWith('.hbs')) {
      handlebars.registerPartial(`${prefix}${entry.name.slice(0, -4)}`, await fs.readFile(filePath, 'utf8'));
    }
  }));
}

export class TemplatePlugin implements Plugin {
  private handlebars = Handlebars.create();

  constructor(private readonly templatesDir: string) {}

  async beforeBuild(): Promise<void> {
    this.handlebars = Handlebars.create();
    await registerPartials(this.handlebars, path.join(this.templatesDir, 'partials'));
  }

  async onFile(page: RenderedPage): Promise<void> {
    const templateName = page.template ?? 'default';
    const source = await readOptional(templatePath(this.templatesDir, templateName));
    if (source === undefined) {
      if (page.template) throw new Error(`Template not found: ${templateName}`);
      page[renderedPage] = renderPage(page);
      return;
    }
    const context = templateContext(page);
    const content = this.handlebars.compile(source)(context);
    if (page.layout === false) {
      page[renderedPage] = content;
      return;
    }
    const layoutName = page.layout ?? 'default';
    const layout = await readOptional(templatePath(path.join(this.templatesDir, 'layouts'), layoutName));
    if (layout === undefined) {
      if (page.layout) throw new Error(`Layout not found: ${layoutName}`);
      page[renderedPage] = content;
      return;
    }
    page[renderedPage] = this.handlebars.compile(layout)({ ...context, body: content });
  }
}
