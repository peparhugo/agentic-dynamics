import fs from 'node:fs/promises';
import path from 'node:path';
import type { Plugin, BuildContext } from '../src/plugin';
import type { Page } from '../src/ssg';

function escapeHtml(value: string): string { return value.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;').replaceAll("'", '&#39;'); }
type Context = Record<string, unknown>;
function value(context: Context, expression: string): unknown {
  const name = expression.trim();
  if (!name) return '';
  if ((name.startsWith('"') && name.endsWith('"')) || (name.startsWith("'") && name.endsWith("'"))) return name.slice(1, -1);
  return name.split('.').reduce<unknown>((current, key) => current && typeof current === 'object' ? (current as Record<string, unknown>)[key] : undefined, context);
}
function text(input: unknown): string { return input === undefined || input === null ? '' : Array.isArray(input) ? input.join(', ') : String(input); }
function handlebars(source: string, context: Context, partials: Map<string, string>): string {
  let result = source.replace(/\{\{#if\s+([^}]+)\}\}([\s\S]*?)\{\{\/if\}\}/g, (_, e: string, c: string) => value(context, e) ? handlebars(c, context, partials) : '');
  result = result.replace(/\{\{#each\s+([^}]+)\}\}([\s\S]*?)\{\{\/each\}\}/g, (_, e: string, c: string) => { const values = value(context, e); return Array.isArray(values) ? values.map((item) => handlebars(c, { ...context, this: item, '.': item }, partials)).join('') : ''; });
  result = result.replace(/\{\{>\s*([\w./-]+)(?:\s+[^}]*)?\s*\}\}/g, (_, n: string) => { const p = partials.get(n) ?? partials.get(path.basename(n, path.extname(n))); return p ? handlebars(p, context, partials) : ''; });
  result = result.replace(/\{\{\{\s*([^}]+)\s*\}\}\}/g, (_, e: string) => text(value(context, e)));
  return result.replace(/\{\{\s*([^}]+)\s*\}\}/g, (_, e: string) => escapeHtml(text(value(context, e))));
}
function ejs(source: string, context: Context, partials: Map<string, string>): string {
  let result = source.replace(/<%[-=]\s*include\(\s*['"]([^'"]+)['"]\s*\)\s*%>/g, (_, n: string) => { const p = partials.get(n) ?? partials.get(path.basename(n, path.extname(n))); return p ? ejs(p, context, partials) : ''; });
  result = result.replace(/<%-\s*([^%]+?)\s*%>/g, (_, e: string) => text(value(context, e)));
  return result.replace(/<%=\s*([^%]+?)\s*%>/g, (_, e: string) => escapeHtml(text(value(context, e))));
}
async function files(directory: string): Promise<Map<string, string>> { const result = new Map<string, string>(); try { for (const entry of await fs.readdir(directory, { withFileTypes: true })) if (entry.isFile() && ['.hbs', '.handlebars', '.ejs'].includes(path.extname(entry.name).toLowerCase())) { const source = await fs.readFile(path.join(directory, entry.name), 'utf8'); result.set(entry.name, source); result.set(path.basename(entry.name, path.extname(entry.name)), source); } } catch (error: unknown) { if ((error as NodeJS.ErrnoException).code !== 'ENOENT') throw error; } return result; }
async function template(directory: string, requested: string | undefined, fallback: string): Promise<{ name: string; source: string } | undefined> { const name = requested ?? fallback; const candidates = path.extname(name) ? [name] : [`${name}.hbs`, `${name}.ejs`, `${name}.handlebars`]; for (const candidate of candidates) try { return { name: candidate, source: await fs.readFile(path.join(directory, candidate), 'utf8') }; } catch (error: unknown) { if ((error as NodeJS.ErrnoException).code !== 'ENOENT') throw error; } if (requested) throw new Error(`Template not found: ${requested}`); return undefined; }

export class TemplatePlugin implements Plugin {
  async onFile(page: Page, context: BuildContext): Promise<Page> {
    const partials = await files(path.join(context.options.templatesDir, 'partials'));
    const data = { ...page.metadata, content: page.html, body: page.html, page, metadata: page.metadata };
    const selected = await template(context.options.templatesDir, page.metadata.template, 'default');
    let document = selected ? (path.extname(selected.name).toLowerCase() === '.ejs' ? ejs(selected.source, data, partials) : handlebars(selected.source, data, partials)) : `<!doctype html>\n<html lang="en">\n<head>\n  <meta charset="utf-8">\n  <meta name="viewport" content="width=device-width, initial-scale=1">\n  <title>${escapeHtml(page.metadata.title)}</title>\n</head>\n<body>\n  <main>\n    <article>\n      <header><h1>${escapeHtml(page.metadata.title)}</h1>${page.metadata.date ? `<time>${escapeHtml(page.metadata.date)}</time>` : ''}${page.metadata.tags.length ? `<ul class="tags">${page.metadata.tags.map((tag) => `<li>${escapeHtml(tag)}</li>`).join('')}</ul>` : ''}</header>\n      ${page.html}\n    </article>\n  </main>\n</body>\n</html>\n`;
    const layout = await template(path.join(context.options.templatesDir, 'layouts'), page.metadata.layout, 'default');
    if (layout) document = path.extname(layout.name).toLowerCase() === '.ejs' ? ejs(layout.source, { ...data, body: document }, partials) : handlebars(layout.source, { ...data, body: document }, partials);
    return { ...page, html: document };
  }
}
export default function templatePlugin(): Plugin { return new TemplatePlugin(); }
