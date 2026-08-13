import { existsSync } from 'node:fs';
import { readdir, readFile, writeFile } from 'node:fs/promises';
import { extname, join, relative } from 'node:path';
import type { Plugin, PluginContext } from './plugin';

type TemplateContext = Record<string, unknown>;

const escapeHtml = (value: string): string => value
  .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  .replace(/"/g, '&quot;').replace(/'/g, '&#39;');

async function templateFiles(directory: string): Promise<string[]> {
  if (!existsSync(directory)) return [];
  const entries = await readdir(directory, { withFileTypes: true });
  const files = await Promise.all(entries.map(async (entry) => {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) return templateFiles(path);
    return extname(entry.name).toLowerCase() === '.hbs' ? [path] : [];
  }));
  return files.flat();
}

function valueAt(context: TemplateContext, path: string): unknown {
  return path.split('.').reduce<unknown>((value, key) => (
    value !== null && typeof value === 'object' ? (value as Record<string, unknown>)[key] : undefined
  ), context);
}

function render(source: string, context: TemplateContext, partials: Map<string, string>): string {
  return source.replace(/{{>\s*([\w./-]+)\s*}}/g, (_match, name: string) => {
    const partial = partials.get(name);
    if (partial === undefined) throw new Error(`Partial does not exist: ${name}`);
    return render(partial, context, partials);
  }).replace(/{{{\s*([\w.]+)\s*}}}/g, (_match, path: string) => String(valueAt(context, path) ?? ''))
    .replace(/{{\s*([\w.]+)\s*}}/g, (_match, path: string) => escapeHtml(String(valueAt(context, path) ?? '')));
}

function layout(title: string, content: string): string {
  return `<!doctype html>\n<html lang="en">\n<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>${escapeHtml(title)}</title></head>\n<body><main>${content}</main></body>\n</html>\n`;
}

export class TemplatePlugin implements Plugin {
  private partials = new Map<string, string>();

  async beforeBuild(context: PluginContext): Promise<void> {
    const partialsDir = join(context.options.templateDir, 'partials');
    const files = await templateFiles(partialsDir);
    this.partials = new Map(await Promise.all(files.map(async (file) => [
      relative(partialsDir, file).replace(/\\/g, '/').replace(/\.hbs$/i, ''), await readFile(file, 'utf8'),
    ] as const)));
  }

  async onFile(page, context): Promise<void> {
    const readTemplate = async (directory: string, name: string): Promise<string | undefined> => {
      const file = join(directory, `${name.replace(/\.hbs$/i, '')}.hbs`);
      return existsSync(file) ? readFile(file, 'utf8') : undefined;
    };
    const template = await readTemplate(context.options.templateDir, typeof page.data.template === 'string' ? page.data.template : 'default');
    const values = { ...page.data, ...page, content: page.html };
    const content = template === undefined ? page.html : render(template, values, this.partials);
    const pageLayout = await readTemplate(join(context.options.templateDir, 'layouts'), typeof page.data.layout === 'string' ? page.data.layout : 'default');
    page.output = pageLayout === undefined ? layout(page.title, content) : render(pageLayout, { ...values, body: content }, this.partials);
  }

  async afterBuild(context: PluginContext): Promise<void> {
    const links = context.pages.map((page) => `<li><a href="${encodeURI(page.slug)}">${escapeHtml(page.title)}</a></li>`).join('\n');
    await writeFile(join(context.options.outputDir, 'index.html'), layout('Index', `<h1>Pages</h1><ul>${links}</ul>`), 'utf8');
  }

}
