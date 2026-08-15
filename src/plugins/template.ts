import fs from 'node:fs/promises';
import path from 'node:path';
import { Page, Plugin, PluginContext } from '../plugin';

type TemplateContext = Record<string, unknown>;

function escapeHtml(value: unknown): string {
  return String(value ?? '').replace(/[&<>"']/g, (character) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[character] as string));
}

function documentHtml(title: string, body: string): string {
  return `<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n<title>${escapeHtml(title)}</title>\n</head>\n<body>\n${body}\n</body>\n</html>\n`;
}

function contextValue(context: TemplateContext, key: string): unknown {
  return key.split('.').reduce<unknown>((value, part) => {
    if (value && typeof value === 'object') return (value as Record<string, unknown>)[part];
    return undefined;
  }, context);
}

function candidates(name: string): string[] { return path.extname(name) ? [name] : [`${name}.hbs`, `${name}.ejs`]; }

async function readTemplate(directory: string, name: string, subdirectory = ''): Promise<{ source: string; extension: string } | undefined> {
  for (const candidate of candidates(name)) {
    const file = path.join(directory, subdirectory, candidate);
    try { return { source: await fs.readFile(file, 'utf8'), extension: path.extname(file).toLowerCase() }; }
    catch (error) { if ((error as NodeJS.ErrnoException).code !== 'ENOENT') throw error; }
  }
  return undefined;
}

async function templateFiles(directory: string): Promise<string[]> {
  try {
    const entries = await fs.readdir(directory, { withFileTypes: true });
    const files: string[] = [];
    for (const entry of entries) {
      const file = path.join(directory, entry.name);
      if (entry.isDirectory()) files.push(...await templateFiles(file));
      else if (/\.(?:hbs|ejs)$/i.test(entry.name)) files.push(file);
    }
    return files;
  } catch (error) { if ((error as NodeJS.ErrnoException).code === 'ENOENT') return []; throw error; }
}

function renderTemplate(source: string, context: TemplateContext, partials: Map<string, string>): string {
  const value = (key: string): string => String(contextValue(context, key.trim()) ?? '');
  const partial = (name: string): string => {
    const key = name.trim().replace(/^partials\//, '').replace(/\.(?:hbs|ejs)$/i, '');
    const partialSource = partials.get(key);
    return partialSource ? renderTemplate(partialSource, context, partials) : '';
  };
  let rendered = source.replace(/{{{\s*([^{}]+?)\s*}}}/g, (_, key: string) => value(key));
  rendered = rendered.replace(/{{>\s*([^{}]+?)\s*}}/g, (_, name: string) => partial(name));
  rendered = rendered.replace(/{{\s*([^{}]+?)\s*}}/g, (_, key: string) => escapeHtml(value(key)));
  rendered = rendered.replace(/<%[-=]\s*include\(\s*['"]([^'"]+)['"]\s*\)\s*%>/g, (_, name: string) => partial(name));
  rendered = rendered.replace(/<%=\s*([^%]+?)\s*%>/g, (_, key: string) => escapeHtml(value(key)));
  return rendered.replace(/<%-\s*([^%]+?)\s*%>/g, (_, key: string) => value(key));
}

export class TemplatePlugin implements Plugin {
  private partials = new Map<string, string>();

  async onStart(context: PluginContext): Promise<void> {
    this.partials = new Map();
    const directory = path.join(context.options.templatesDir, 'partials');
    for (const file of await templateFiles(directory)) {
      const relative = path.relative(directory, file);
      this.partials.set(relative.replace(/\.(?:hbs|ejs)$/i, '').split(path.sep).join('/'), await fs.readFile(file, 'utf8'));
    }
  }

  async onFile(page: Page, context: PluginContext): Promise<void> {
    const requested = typeof page.data.template === 'string' ? page.data.template : undefined;
    const template = requested ? await readTemplate(context.options.templatesDir, requested) : undefined;
    if (requested && !template) throw new Error(`Template not found: ${requested}`);
    const fallback = template ? undefined : await readTemplate(context.options.templatesDir, context.options.defaultTemplate);
    const title = typeof page.data.title === 'string' ? page.data.title : path.basename(page.url, '.html');
    const templateContext = { ...page.data, title, url: page.url, body: page.body, content: page.content, html: page.html };
    let rendered = renderTemplate((template ?? fallback)?.source ?? page.body, templateContext, this.partials);
    const layoutName = typeof page.data.layout === 'string' ? page.data.layout : undefined;
    if (layoutName) {
      const layout = await readTemplate(context.options.templatesDir, layoutName, 'layouts');
      if (!layout) throw new Error(`Template not found: layouts/${layoutName}`);
      rendered = renderTemplate(layout.source, { ...templateContext, body: rendered }, this.partials);
    }
    page.rendered = rendered;
    const hasTemplate = Boolean(requested || page.data.layout || fallback);
    const destination = path.join(context.options.outputDir, page.url);
    await fs.mkdir(path.dirname(destination), { recursive: true });
    await fs.writeFile(destination, hasTemplate || /^\s*<!doctype html>/i.test(rendered) ? rendered : documentHtml(title, rendered), 'utf8');
  }

  async afterBuild(context: PluginContext): Promise<void> {
    const listing = context.pages.map((page) => {
      const title = typeof page.data.title === 'string' ? page.data.title : path.basename(page.url, '.html');
      return `<li><a href="${escapeHtml(page.url)}">${escapeHtml(title)}</a></li>`;
    }).join('\n');
    await fs.writeFile(path.join(context.options.outputDir, 'index.html'), documentHtml('Index', `<main>\n<h1>Pages</h1>\n<ul>\n${listing}\n</ul>\n</main>`), 'utf8');
  }
}

export default TemplatePlugin;
