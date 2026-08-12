import { promises as fs } from 'node:fs';
import path from 'node:path';
import { BuildContext, Plugin } from '../plugin';
import type { Page } from '../index';

function escapeHtml(value: string): string { return value.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c] as string); }
type Context = Record<string, unknown>;
function lookup(context: Context, key: string): unknown { return key.trim().split('.').reduce<unknown>((v, p) => v && typeof v === 'object' ? (v as Context)[p] : undefined, context); }
function value(input: unknown): string { return input === undefined || input === null ? '' : String(input); }
function handlebars(source: string, context: Context, partials: Map<string, string>): string {
  let result = source.replace(/{{>\s*([\w./-]+)\s*}}/g, (_m, name: string) => { const p = partials.get(name) ?? partials.get(name.replace(/\.(?:hbs|ejs)$/i, '')); return p === undefined ? '' : handlebars(p, context, partials); });
  let previous: string;
  do { previous = result; result = result.replace(/{{#if\s+([^}]+)}}([\s\S]*?){{\/if}}/g, (_m, k, c) => lookup(context, k) ? c : ''); result = result.replace(/{{#each\s+([^}]+)}}([\s\S]*?){{\/each}}/g, (_m, k, c) => { const values = lookup(context, k); return Array.isArray(values) ? values.map((v) => handlebars(c, { ...context, this: v, ...(typeof v === 'object' && v ? v : {}) }, partials)).join('') : ''; }); } while (result !== previous);
  result = result.replace(/{{{\s*([^}]+)\s*}}}/g, (_m, k) => value(lookup(context, k)));
  return result.replace(/{{\s*([^#/>][^}]*)\s*}}/g, (_m, k) => escapeHtml(value(lookup(context, k))));
}
function ejs(source: string, context: Context, partials: Map<string, string>): string {
  const include = (name: string): string => { const key = name.replace(/^partials\//, '').replace(/\.(?:hbs|ejs)$/i, ''); const p = partials.get(key) ?? partials.get(name); return p === undefined ? '' : ejs(p, context, partials); };
  return source.replace(/<%([=-])?([\s\S]*?)%>/g, (_m, mode, expression) => { const code = expression.trim(); if (code.startsWith('include(')) { const name = code.match(/include\(\s*['"]([^'"]+)['"]\s*\)/)?.[1]; return name ? include(name) : ''; } if (mode === '=' || mode === '-') { try { const result = Function('context', `with (context) { return (${code}); }`)(context); return mode === '=' ? escapeHtml(value(result)) : value(result); } catch { return ''; } } return ''; });
}
async function template(directory: string, requested: string, category?: string): Promise<{ source: string; extension: string } | undefined> { const name = requested.replace(/^[/\\]+/, '').replace(/\.(hbs|ejs)$/i, ''); const base = category ? path.join(directory, category, name) : path.join(directory, name); for (const extension of ['.hbs', '.ejs']) { try { return { source: await fs.readFile(`${base}${extension}`, 'utf8'), extension }; } catch { /* try the other engine */ } } return undefined; }
async function partials(directory: string): Promise<Map<string, string>> { const result = new Map<string, string>(); let entries; try { entries = await fs.readdir(path.join(directory, 'partials'), { withFileTypes: true }); } catch { return result; } for (const entry of entries) if (entry.isFile() && /\.(hbs|ejs)$/i.test(entry.name)) result.set(entry.name.replace(/\.(hbs|ejs)$/i, ''), await fs.readFile(path.join(directory, 'partials', entry.name), 'utf8')); return result; }
function document(title: string, body: string): string { return `<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n<title>${escapeHtml(title)}</title>\n</head>\n<body>\n${body}\n</body>\n</html>\n`; }

export class TemplatePlugin implements Plugin {
  async afterBuild(context: BuildContext): Promise<void> {
    const partialMap = await partials(context.templatesDir);
    const defaultTemplate = context.options.defaultTemplate;
    await Promise.all(context.pages.map(async (page: Page) => {
      const outputPath = path.join(context.outputDir, page.slug); await fs.mkdir(path.dirname(outputPath), { recursive: true });
      const cached = context.cache.pages[page.sourcePath];
      if (context.renderCacheEnabled && context.stats.pagesSkipped > 0 && cached?.renderedHtml !== undefined && cached.page.slug === page.slug) { await fs.writeFile(outputPath, cached.renderedHtml); return; }
      const started = Date.now();
      const metadata = [page.date ? `<p class="date">${escapeHtml(page.date)}</p>` : '', page.tags.length ? `<p class="tags">${page.tags.map(escapeHtml).join(', ')}</p>` : ''].join('');
      const content = `<main><h1>${escapeHtml(page.title)}</h1>${metadata}${page.html}</main>`;
      const data: Context = { ...(page.data ?? {}), ...page, content, body: content }; const selected = await template(context.templatesDir, page.template ?? defaultTemplate); let body = selected ? (selected.extension === '.ejs' ? ejs(selected.source, data, partialMap) : handlebars(selected.source, data, partialMap)) : content;
      const layout = await template(context.templatesDir, page.layout ?? 'default', 'layouts'); if (layout) { const layoutData = { ...data, body }; body = layout.extension === '.ejs' ? ejs(layout.source, layoutData, partialMap) : handlebars(layout.source, layoutData, partialMap); }
      const rendered = selected || layout ? body : document(page.title, body); await fs.writeFile(outputPath, rendered);
      if (cached) { cached.page = page; cached.renderedHtml = rendered; cached.renderDurationMs = Date.now() - started; }
    }));
    const links = context.pages.map((p) => `<li><a href="${escapeHtml(p.slug)}">${escapeHtml(p.title)}</a>${p.date ? ` <time>${escapeHtml(p.date)}</time>` : ''}</li>`).join('\n');
    await fs.writeFile(path.join(context.outputDir, 'index.html'), document('Home', `<main><h1>Pages</h1><ul>${links}</ul></main>`));
  }
}
