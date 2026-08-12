import fs from 'node:fs';
import path from 'node:path';

type TemplateContext = Record<string, unknown>;

function templateValue(value: unknown): string {
  if (value === null || value === undefined || value === false) return '';
  if (Array.isArray(value)) return value.join(', ');
  return String(value);
}

function lookup(context: TemplateContext, key: string): unknown {
  if (key === 'this' || key === '.') return context;
  return key.split('.').reduce<unknown>((value, part) => {
    if (value && typeof value === 'object') return (value as Record<string, unknown>)[part];
    return undefined;
  }, context);
}

function readPartial(directory: string, name: string): string {
  const base = path.join(directory, 'partials');
  const candidate = path.resolve(base, name.endsWith('.hbs') ? name : `${name}.hbs`);
  if (!candidate.startsWith(`${path.resolve(base)}${path.sep}`)) throw new Error(`Invalid template path: ${name}`);
  if (!fs.existsSync(candidate)) throw new Error(`Partial not found: ${name}`);
  return fs.readFileSync(candidate, 'utf8');
}

function escapeHtml(value: string): string {
  return value.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

export function renderTemplate(source: string, context: TemplateContext, templatesDir?: string): string {
  const directory = templatesDir ?? path.resolve('./templates');
  let rendered = source.replace(/\{\{!([\s\S]*?)\}\}/g, '');
  rendered = rendered.replace(/\{\{>\s*([^\s}]+)(?:\s+([^}]+))?\s*\}\}/g, (_match, name: string, partialContext?: string) => {
    const values = partialContext ? lookup(context, partialContext.trim()) : context;
    const child = values && typeof values === 'object' ? values as TemplateContext : context;
    return renderTemplate(readPartial(directory, name), child, directory);
  });
  rendered = rendered.replace(/\{\{\{\s*([^}]+?)\s*\}\}\}/g, (_match, key: string) => templateValue(lookup(context, key.trim())));
  return rendered.replace(/\{\{\s*([^}]+?)\s*\}\}/g, (_match, key: string) => escapeHtml(templateValue(lookup(context, key.trim()))));
}

export { escapeHtml };
