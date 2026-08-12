import { promises as fs } from 'node:fs';
import path from 'node:path';
import type { BuildContext, Plugin } from '../plugin';
import type { Page } from '../generator';

type Context = Record<string, unknown>;
type TemplateFile = { source: string; filename: string };
const escapeHtml = (value: string): string => value.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
const document = (title: string, body: string): string => `<!doctype html>\n<html lang="en">\n<head>\n  <meta charset="utf-8">\n  <meta name="viewport" content="width=device-width, initial-scale=1">\n  <title>${escapeHtml(title)}</title>\n</head>\n<body>\n${body}\n</body>\n</html>\n`;
const lookup = (context: Context, expression: string): unknown => {
  const key = expression.trim().replace(/^this\.?/, '');
  if (!key || key === '.') return context;
  return key.split('.').reduce<unknown>((value, part) => part === 'this' ? value : value && typeof value === 'object' ? (value as Context)[part] : undefined, context);
};
function render(source: string, filename: string, context: Context, partials: Map<string, TemplateFile>): string {
  const handlebars = (input: string, values: Context): string => {
    input = input.replace(/{{#(if|unless|each)\s+([^}]+)}}([\s\S]*?){{\/\1}}/g, (_m, kind: string, expression: string, inner: string) => {
      const value = lookup(values, expression);
      if (kind === 'each') return Array.isArray(value) ? value.map((item, index) => handlebars(inner, { ...values, this: item, '@index': index })).join('') : '';
      const truthy = Array.isArray(value) ? value.length > 0 : Boolean(value);
      return (kind === 'if' ? truthy : !truthy) ? handlebars(inner, values) : '';
    });
    input = input.replace(/{{>\s*([^}\s]+)\s*}}/g, (_m, name: string) => { const partial = partials.get(name.replace(/\.(hbs|ejs)$/i, '')); return partial ? render(partial.source, partial.filename, values, partials) : ''; });
    input = input.replace(/{{{\s*([^}]+)\s*}}}/g, (_m, expression: string) => String(lookup(values, expression) ?? ''));
    return input.replace(/{{\s*([^}]+)\s*}}/g, (_m, expression: string) => escapeHtml(String(lookup(values, expression) ?? '')));
  };
  if (!filename.endsWith('.ejs')) return handlebars(source, context);
  const include = (name: string) => { const partial = partials.get(name.replace(/^.*[\\/]partials[\\/]?/, '').replace(/\.(hbs|ejs)$/i, '')); return partial ? render(partial.source, partial.filename, context, partials) : ''; };
  return source.replace(/<%([=-])?([\s\S]*?)%>/g, (_m, mode: string | undefined, expression: string) => {
    const value = expression.trim();
    if (value.startsWith('include(')) return include(value.match(/include\(['"]([^'"]+)['"]\)/)?.[1] ?? '');
    if (mode !== '=' && mode !== '-') return '';
    try { const result = Function('context', `with (context) { return (${value}); }`)(context); return mode === '=' ? escapeHtml(String(result ?? '')) : String(result ?? ''); } catch { return ''; }
  });
}
async function readTemplates(directory: string) {
  const result = { templates: new Map<string, TemplateFile>(), layouts: new Map<string, TemplateFile>(), partials: new Map<string, TemplateFile>() };
  const load = async (folder: string, target: Map<string, TemplateFile>) => { let entries; try { entries = await fs.readdir(folder, { withFileTypes: true }); } catch { return; } for (const entry of entries) if (entry.isFile() && /\.(hbs|ejs)$/i.test(entry.name)) target.set(entry.name.replace(/\.(hbs|ejs)$/i, ''), { source: await fs.readFile(path.join(folder, entry.name), 'utf8'), filename: entry.name }); };
  await load(directory, result.templates); await load(path.join(directory, 'layouts'), result.layouts); await load(path.join(directory, 'partials'), result.partials); return result;
}

export function TemplatePlugin(): Plugin {
  return { name: 'templates', async beforeBuild(context) { (context as BuildContext & { templateFiles?: Awaited<ReturnType<typeof readTemplates>> }).templateFiles = await readTemplates(context.templatesDir); }, async onFile(page, context) {
    const files = (context as BuildContext & { templateFiles: Awaited<ReturnType<typeof readTemplates>> }).templateFiles;
    const metadata = [page.date ? `<time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : '', page.tags.length ? `<p>Tags: ${page.tags.map(escapeHtml).join(', ')}</p>` : ''].filter(Boolean).join('\n');
    const article = `<article>\n<h1>${escapeHtml(page.title)}</h1>\n${metadata}\n${page.html}\n</article>`;
    const contextValues: Context = { ...page.frontmatter, ...page, content: page.html, body: article, metadata };
    const templateName = page.template?.replace(/\.(hbs|ejs)$/i, '') ?? 'default';
    const template = files.templates.get(templateName); let output = template ? render(template.source, template.filename, contextValues, files.partials) : article;
    const layoutName = page.layout?.replace(/\.(hbs|ejs)$/i, '') ?? (files.layouts.has('default') ? 'default' : undefined); const layout = layoutName ? files.layouts.get(layoutName) : undefined;
    if (layout) output = render(layout.source, layout.filename, { ...contextValues, body: output }, files.partials);
    if (!template && !layout) output = document(page.title, output);
    context.outputs.set(page.outputPath, output);
  }, async afterBuild(context) { const links = context.pages.map((page) => `<li><a href="${page.outputPath.replaceAll(path.sep, '/')}">${escapeHtml(page.title)}</a>${page.date ? ` <time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : ''}</li>`).join('\n'); context.outputs.set('index.html', document('Home', `<h1>Pages</h1>\n<ul>\n${links}\n</ul>`)); } };
}

export default TemplatePlugin;
