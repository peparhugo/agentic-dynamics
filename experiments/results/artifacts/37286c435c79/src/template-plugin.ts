import { promises as fs } from 'node:fs';
import path from 'node:path';
import type { Plugin } from './plugin';
import type { Page } from './generator';
import { pageMetadata, type Frontmatter } from './markdown-plugin';

type TemplateContext = Record<string, unknown>;

const escapeHtml = (value: string): string => value.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;').replaceAll("'", '&#39;');
const valueAt = (context: TemplateContext, expression: string): unknown => {
  const name = expression.trim();
  if (name === 'this' || name === '.') return context.this ?? context;
  return name.split('.').reduce<unknown>((value, part) => value && typeof value === 'object' ? (value as Record<string, unknown>)[part] : undefined, context);
};
const stringValue = (value: unknown): string => value == null ? '' : String(value);

const templateFile = async (directory: string, name: string, subdirectory = ''): Promise<string | undefined> => {
  const requested = name.trim();
  const candidates = path.extname(requested) ? [requested] : [`${requested}.hbs`, `${requested}.ejs`];
  for (const candidate of candidates) {
    const file = path.join(directory, subdirectory, candidate);
    try { if ((await fs.stat(file)).isFile()) return file; } catch { /* Try the next extension. */ }
  }
  return undefined;
};

const renderTemplate = (source: string, context: TemplateContext, partials: Record<string, string>): string => {
  const render = (input: string, values: TemplateContext): string => {
    let output = input;
    output = output.replace(/{{#each\s+([^}]+)}}([\s\S]*?){{\/each}}/g, (_m, expression: string, body: string) => {
      const items = valueAt(values, expression);
      return Array.isArray(items) ? items.map((item, index) => render(body, { ...values, this: item, '@index': index })).join('') : '';
    });
    output = output.replace(/{{#if\s+([^}]+)}}([\s\S]*?){{\/if}}/g, (_m, expression: string, body: string) => valueAt(values, expression) ? render(body, values) : '');
    output = output.replace(/{{>\s*([\w./-]+)\s*}}/g, (_m, name: string) => { const partial = partials[name] ?? partials[path.basename(name)]; return partial ? render(partial, values) : ''; });
    output = output.replace(/<%-\s*include\(['"]([^'"]+)['"]\)\s*%>/g, (_m, name: string) => { const partial = partials[name] ?? partials[path.basename(name)]; return partial ? render(partial, values) : ''; });
    output = output.replace(/{{{\s*([^}]+)\s*}}}/g, (_m, expression: string) => stringValue(valueAt(values, expression)));
    output = output.replace(/{{\s*([^{}#\/>][^{}]*)\s*}}/g, (_m, expression: string) => escapeHtml(stringValue(valueAt(values, expression))));
    output = output.replace(/<%=\s*([^%]+)\s*%>/g, (_m, expression: string) => escapeHtml(stringValue(valueAt(values, expression))));
    return output.replace(/<%-\s*([^%]+)\s*%>/g, (_m, expression: string) => stringValue(valueAt(values, expression)));
  };
  return render(source, context);
};

async function loadPartials(directory: string): Promise<Record<string, string>> {
  const result: Record<string, string> = {};
  let entries: import('node:fs').Dirent[] = [];
  try { entries = await fs.readdir(path.join(directory, 'partials'), { withFileTypes: true }); } catch { return result; }
  for (const entry of entries) if (entry.isFile() && /\.(hbs|ejs)$/i.test(entry.name)) result[entry.name.replace(/\.(hbs|ejs)$/i, '')] = await fs.readFile(path.join(directory, 'partials', entry.name), 'utf8');
  return result;
}

const frontmatterName = (value: unknown): string | undefined => typeof value === 'string' && value.trim() ? value.trim() : undefined;
const fallbackDocument = (page: Page): string => {
  const date = page.date ? `<time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : '';
  const tags = page.tags.length ? `<ul class="tags">${page.tags.map((tag) => `<li>${escapeHtml(tag)}</li>`).join('')}</ul>` : '';
  return `<!doctype html>\n<html lang="en">\n<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>${escapeHtml(page.title)}</title></head>\n<body><main><h1>${escapeHtml(page.title)}</h1>${date}${tags}<article>${page.html}</article></main></body>\n</html>\n`;
};

export const TemplatePlugin: Plugin = {
  async afterBuild(context) {
    const templatesDir = path.resolve(context.options.templatesDir ?? './templates');
    const partials = await loadPartials(templatesDir);
     const index = `<!doctype html>\n<html lang="en">\n<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Index</title></head>\n<body><main><h1>Pages</h1><ul>${context.pages.map((page) => `<li><a href="${encodeURI(page.outputPath)}">${escapeHtml(page.title)}</a>${page.date ? ` <time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : ''}</li>`).join('')}</ul></main></body>\n</html>\n`;
    await fs.writeFile(path.join(context.options.outputDir!, 'index.html'), index);
    for (const page of context.pages) {
      if (context.build && !context.build.changedOutputs.has(page.outputPath)) continue;
      const metadata: Frontmatter = pageMetadata.get(page) ?? {};
      const selected = frontmatterName(metadata.template);
      const templatePath = selected ? await templateFile(templatesDir, selected) : await templateFile(templatesDir, 'default');
      if (selected && !templatePath) throw new Error(`Template not found: ${selected}`);
      const values = { ...metadata, title: page.title, date: page.date, tags: page.tags, content: page.html, body: page.html, html: page.html, page };
      let document = templatePath ? renderTemplate(await fs.readFile(templatePath, 'utf8'), values, partials) : fallbackDocument(page);
      const layout = frontmatterName(metadata.layout);
      if (layout && layout !== 'none') {
        const layoutPath = await templateFile(templatesDir, layout, 'layouts');
        if (!layoutPath) throw new Error(`Layout template not found: ${layout}`);
        document = renderTemplate(await fs.readFile(layoutPath, 'utf8'), { ...values, body: document, content: document }, partials);
      }
      const destination = path.join(context.options.outputDir!, page.outputPath);
      await fs.mkdir(path.dirname(destination), { recursive: true });
      await fs.writeFile(destination, document);
    }
  },
};
