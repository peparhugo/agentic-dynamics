import { readdir, readFile } from 'node:fs/promises';
import { isAbsolute, join, relative, resolve, sep } from 'node:path';
import Handlebars from 'handlebars';
import { PageMetadata } from './types';

const DEFAULT_TEMPLATE = `<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{{title}}</title></head>
<body><main><article><h1>{{title}}</h1>{{{dateHtml}}}{{{tagsHtml}}}{{{body}}}</article></main></body>
</html>`;

function escapeHtml(value: string): string {
  return value.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function templateName(value: unknown, kind: string): string | undefined {
  if (value === undefined) return undefined;
  if (typeof value !== 'string' || !value || isAbsolute(value) || value.split(/[\\/]/).includes('..')) {
    throw new Error(`Invalid ${kind} template name`);
  }
  return value.endsWith('.hbs') ? value.slice(0, -4) : value;
}

async function readTemplate(path: string): Promise<string | undefined> {
  try {
    return await readFile(path, 'utf8');
  } catch (error: unknown) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return undefined;
    throw error;
  }
}

async function loadPartials(directory: string, root = directory): Promise<Array<[string, string]>> {
  const partials: Array<[string, string]> = [];
  try {
    const entries = await readdir(directory, { withFileTypes: true });
    await Promise.all(entries.map(async (entry) => {
      const path = join(directory, entry.name);
      if (entry.isDirectory()) {
        partials.push(...await loadPartials(path, root));
      } else if (entry.isFile() && entry.name.endsWith('.hbs')) {
        const name = relative(root, path).split(sep).join('/').slice(0, -4);
        partials.push([name, await readFile(path, 'utf8')]);
      }
    }));
  } catch (error: unknown) {
    if ((error as NodeJS.ErrnoException).code !== 'ENOENT') throw error;
  }
  return partials;
}

export async function renderTemplatePage(metadata: PageMetadata, body: string, templatesDirectory: string): Promise<string> {
  const root = resolve(templatesDirectory);
  const template = templateName(metadata.template, 'page') ?? 'page';
  const layout = templateName(metadata.layout, 'layout');
  const pageSource = await readTemplate(join(root, `${template}.hbs`));
  if (pageSource === undefined && template !== 'page') throw new Error(`Page template not found: ${template}`);

  const dateHtml = metadata.date ? `<time datetime="${escapeHtml(metadata.date)}">${escapeHtml(metadata.date)}</time>` : '';
  const tagsHtml = metadata.tags.length ? `<ul class="tags">${metadata.tags.map((tag) => `<li>${escapeHtml(tag)}</li>`).join('')}</ul>` : '';
  const context = { ...metadata, page: metadata, body, dateHtml, tagsHtml };
  const handlebars = Handlebars.create();
  const partials = await loadPartials(join(root, 'partials'));
  for (const [name, source] of partials) handlebars.registerPartial(name, source);
  const page = handlebars.compile(pageSource ?? DEFAULT_TEMPLATE)(context);
  if (!layout) return page;

  const layoutSource = await readTemplate(join(root, 'layouts', `${layout}.hbs`));
  if (layoutSource === undefined) throw new Error(`Layout template not found: ${layout}`);
  return handlebars.compile(layoutSource)({ ...context, body: page });
}
