import { readdir, readFile } from 'node:fs/promises';
import path from 'node:path';
import Handlebars from 'handlebars';
import ejs from 'ejs';
import type { PluginContext, Plugin } from '../plugin';
import type { Page } from '../generator';

type Template = { source: string; path: string; engine: 'hbs' | 'ejs' };
const titleOf = (page: Page): string => page.metadata.title || path.basename(page.sourcePath, path.extname(page.sourcePath));
const escapeHtml = (value: string): string => value.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
  .replaceAll('"', '&quot;').replaceAll("'", '&#39;');

async function filesWithExtensions(directory: string, extensions: string[]): Promise<string[]> {
  const entries = await readdir(directory, { withFileTypes: true });
  const files: string[] = [];
  for (const entry of entries) {
    const file = path.join(directory, entry.name);
    if (entry.isDirectory()) files.push(...await filesWithExtensions(file, extensions));
    else if (entry.isFile() && extensions.includes(path.extname(entry.name).toLowerCase())) files.push(file);
  }
  return files;
}

async function findTemplate(directory: string, name: string, subdirectory = ''): Promise<Template | undefined> {
  for (const filename of path.extname(name) ? [name] : [`${name}.hbs`, `${name}.ejs`]) {
    const templatePath = path.join(directory, subdirectory, filename);
    try { return { source: await readFile(templatePath, 'utf8'), path: templatePath, engine: path.extname(templatePath).toLowerCase() === '.ejs' ? 'ejs' : 'hbs' }; }
    catch (error) { if ((error as NodeJS.ErrnoException).code !== 'ENOENT') throw error; }
  }
  return undefined;
}

function fallback(page: Page): string {
  const title = escapeHtml(titleOf(page));
  const date = page.metadata.date ? `<time>${escapeHtml(String(page.metadata.date))}</time>` : '';
  const tags = page.metadata.tags.length ? `<ul class="tags">${page.metadata.tags.map((tag) => `<li>${escapeHtml(tag)}</li>`).join('')}</ul>` : '';
  return `<!doctype html>\n<html lang="en">\n<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>${title}</title></head>\n<body><main><h1>${title}</h1>${date}${tags}<article>${page.content}</article></main></body>\n</html>\n`;
}

export class TemplatePlugin implements Plugin {
  async beforeBuild(context: PluginContext): Promise<void> {
    const partialDir = path.join(context.templatesDir, 'partials');
    const files = await filesWithExtensions(partialDir, ['.hbs', '.ejs']).catch(() => []);
    for (const file of files) if (path.extname(file).toLowerCase() === '.hbs') {
      const name = path.relative(partialDir, file).replace(/\.(hbs|ejs)$/i, '').split(path.sep).join('/');
      const source = await readFile(file, 'utf8');
      Handlebars.registerPartial(name, source); Handlebars.registerPartial(`partials/${name}`, source);
    }
  }

  async onFile(page: Page, context: PluginContext): Promise<void> {
    const requested = typeof page.metadata.template === 'string' ? page.metadata.template : context.options.defaultTemplate || 'default';
    const template = await findTemplate(context.templatesDir, requested);
    if (!template) {
      if (typeof page.metadata.template === 'string') throw new Error(`Template not found: ${requested}`);
      context.emitFile(page.outputPath, fallback(page)); return;
    }
    const data = { ...page.metadata, title: titleOf(page), content: page.content, page };
    const render = async (item: Template, values: Record<string, unknown>) => item.engine === 'hbs' ? Handlebars.compile(item.source)(values) : ejs.render(item.source, values, { filename: item.path });
    let output = await render(template, data);
    const layoutName = typeof page.metadata.layout === 'string' ? page.metadata.layout : context.options.defaultLayout;
    if (layoutName) {
      const layout = await findTemplate(context.templatesDir, layoutName, 'layouts');
      if (!layout) throw new Error(`Layout not found: ${layoutName}`);
      output = await render(layout, { ...data, body: output });
    }
    context.emitFile(page.outputPath, output);
  }

  async afterBuild(context: PluginContext): Promise<void> {
    const escape = (value: string) => escapeHtml(value);
    const items = context.pages.map((page) => `<li><a href="${escape(page.url)}">${escape(titleOf(page))}</a></li>`).join('');
    context.emitFile(path.join(context.outputDir, 'index.html'), `<!doctype html>\n<html lang="en">\n<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Index</title></head>\n<body><main><h1>Pages</h1><ul>${items}</ul></main></body>\n</html>\n`);
  }
}

export default TemplatePlugin;
