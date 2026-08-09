import fs from 'node:fs';
import path from 'node:path';
import Handlebars from 'handlebars';
import fg from 'fast-glob';

export type Templates = {
  layouts: Map<string, Handlebars.TemplateDelegate>;
};

export function loadTemplates(templatesDir: string): Templates {
  const layoutsDir = path.join(templatesDir, 'layouts');
  const partialsDir = path.join(templatesDir, 'partials');

  // Register partials
  if (fs.existsSync(partialsDir)) {
    const partialPaths = fg.sync('**/*.hbs', { cwd: partialsDir, dot: false });
    for (const rel of partialPaths) {
      const full = path.join(partialsDir, rel);
      const name = rel.replace(/\.hbs$/, '').split(path.sep).join('/');
      Handlebars.registerPartial(name, fs.readFileSync(full, 'utf8'));
    }
  }

  // Load layouts
  const layouts = new Map<string, Handlebars.TemplateDelegate>();
  if (fs.existsSync(layoutsDir)) {
    const layoutPaths = fg.sync('**/*.hbs', { cwd: layoutsDir, dot: false });
    for (const rel of layoutPaths) {
      const full = path.join(layoutsDir, rel);
      const name = rel.replace(/\.hbs$/, '').split(path.sep).join('/');
      const tpl = Handlebars.compile(fs.readFileSync(full, 'utf8'));
      layouts.set(name, tpl);
    }
  }

  // Basic helpers
  Handlebars.registerHelper('formatDate', function (date: any) {
    try {
      const d = new Date(date);
      return isNaN(d.getTime()) ? '' : d.toISOString().slice(0, 10);
    } catch {
      return '';
    }
  });

  return { layouts };
}

export function renderWithLayout(layouts: Templates['layouts'], layoutName: string, context: any): string {
  const tpl = layouts.get(layoutName) || layouts.get('default');
  if (!tpl) {
    // Fallback minimal HTML if no layouts are present
    const title = context?.page?.title || 'Untitled';
    const body = context?.body || '';
    return `<!doctype html><html><head><meta charset="utf-8"><title>${escapeHtml(title)}</title><meta name="viewport" content="width=device-width, initial-scale=1"></head><body>${body}</body></html>`;
  }
  return tpl(context);
}

export function escapeHtml(str: string): string {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
