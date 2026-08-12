import fs from 'fs/promises';
import path from 'path';
import type { Page } from '../site-generator';
import { Plugin, PluginContext } from '../plugin';
import { pageFrontmatter } from './markdown';

type TemplateValue = Record<string, unknown>;
const renderedPages = new WeakMap<Page, string>();
export function getRenderedHtml(page: Page): string | undefined { return renderedPages.get(page); }
function escapeHtml(value: string): string { return value.replace(/[&<>"']/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[character] as string)); }
function lookup(context: TemplateValue, key: string): unknown {
  if (key === 'this' || key === '.') return context;
  return key.split('.').reduce<unknown>((value, part) => part === 'this' ? value : value && typeof value === 'object' ? (value as TemplateValue)[part] : undefined, context);
}
function renderTemplate(source: string, context: TemplateValue, partials: Map<string, string>): string {
  const renderBlock = (input: string, scope: TemplateValue): string => {
    let output = input.replace(/{{#(if|each)\s+([^}]+)}}([\s\S]*?){{\/\1}}/g, (_m, type: string, expression: string, content: string) => {
      const value = lookup(scope, expression.trim());
      if (type === 'if') return Boolean(value) && (!Array.isArray(value) || value.length > 0) ? renderBlock(content, scope) : '';
      return Array.isArray(value) ? value.map((item) => renderBlock(content, typeof item === 'object' && item !== null ? { ...scope, ...(item as TemplateValue), this: item } : { ...scope, this: item })).join('') : '';
    });
    output = output.replace(/{{>\s*([\w./-]+)\s*}}/g, (_m, name: string) => { const partial = partials.get(name); return partial === undefined ? '' : renderBlock(partial, scope); });
    output = output.replace(/{{{\s*([^}]+?)\s*}}}/g, (_m, expression: string) => { const value = lookup(scope, expression.trim()); return value == null ? '' : String(value); });
    return output.replace(/{{\s*([^{}]+?)\s*}}/g, (_m, expression: string) => escapeHtml(lookup(scope, expression.trim()) == null ? '' : String(lookup(scope, expression.trim()))));
  };
  return renderBlock(source, context);
}
async function loadTemplates(directory: string): Promise<Map<string, string>> {
  const result = new Map<string, string>();
  let entries;
  try { entries = await fs.readdir(directory, { withFileTypes: true }); } catch (error) { if ((error as NodeJS.ErrnoException).code === 'ENOENT') return result; throw error; }
  for (const entry of entries) if (entry.isFile() && /\.(hbs|ejs)$/i.test(entry.name)) result.set(entry.name.replace(/\.(hbs|ejs)$/i, ''), await fs.readFile(path.join(directory, entry.name), 'utf8'));
  return result;
}

export class TemplatePlugin implements Plugin {
  async onFile(page: Page, context: PluginContext): Promise<Page> {
    const templates = await loadTemplates(context.options.templatesDir);
    const partials = await loadTemplates(path.join(context.options.templatesDir, 'partials'));
    const selected = page.template || context.options.defaultTemplate;
    const template = templates.get(selected.replace(/\.(hbs|ejs)$/i, ''));
    if (!template) { if (page.template) throw new Error(`Template not found: ${page.template}`); return page; }
    const base = { ...pageFrontmatter.get(page), page, title: page.title, date: page.date, tags: page.tags, body: page.html };
    let rendered = renderTemplate(template, base, partials);
    if (page.layout) {
      const layouts = await loadTemplates(path.join(context.options.templatesDir, 'layouts'));
      const layout = layouts.get(page.layout.replace(/\.(hbs|ejs)$/i, ''));
      if (!layout) throw new Error(`Layout not found: ${page.layout}`);
      rendered = renderTemplate(layout, { ...base, body: rendered }, partials);
    }
    renderedPages.set(page, rendered);
    return page;
  }
}
