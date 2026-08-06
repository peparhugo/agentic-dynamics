import Handlebars from 'handlebars';
import fs from 'node:fs';
import path from 'node:path';

export interface TemplateEngine {
  /** Render a named page template (e.g. "post", "index", "tag") wrapped in its layout. */
  render(templateName: string, context: Record<string, unknown>, layoutName?: string): string;
  hasTemplate(name: string): boolean;
}

/**
 * Template directory conventions:
 *   templates/*.hbs            page templates (post.hbs, index.hbs, tag.hbs, ...)
 *   templates/layouts/*.hbs    layouts; page output is exposed as {{{body}}}
 *   templates/partials/*.hbs   partials registered by filename ({{> header}})
 *
 * Layout resolution: explicit layoutName arg > context.layout > "default" > none.
 */
export function createTemplateEngine(templatesDir: string): TemplateEngine {
  const hbs = Handlebars.create();
  const templates = new Map<string, Handlebars.TemplateDelegate>();
  const layouts = new Map<string, Handlebars.TemplateDelegate>();

  registerHelpers(hbs);

  const readHbs = (dir: string): Array<[string, string]> => {
    if (!fs.existsSync(dir)) return [];
    return fs
      .readdirSync(dir)
      .filter((f) => f.endsWith('.hbs') || f.endsWith('.handlebars'))
      .map((f) => [f.replace(/\.(hbs|handlebars)$/, ''), fs.readFileSync(path.join(dir, f), 'utf8')]);
  };

  for (const [name, src] of readHbs(templatesDir)) templates.set(name, hbs.compile(src));
  for (const [name, src] of readHbs(path.join(templatesDir, 'layouts'))) layouts.set(name, hbs.compile(src));
  for (const [name, src] of readHbs(path.join(templatesDir, 'partials'))) hbs.registerPartial(name, src);

  return {
    hasTemplate: (name) => templates.has(name),
    render(templateName, context, layoutName) {
      const template = templates.get(templateName);
      if (!template) {
        throw new Error(`Template not found: "${templateName}" in ${templatesDir}`);
      }
      const body = template(context);
      const layoutKey =
        layoutName ?? (typeof context.layout === 'string' ? context.layout : undefined) ?? 'default';
      const layout = layouts.get(layoutKey);
      if (layoutName && !layouts.get(layoutName)) {
        throw new Error(`Layout not found: "${layoutName}" in ${path.join(templatesDir, 'layouts')}`);
      }
      if (!layout) return body;
      return layout({ ...context, body });
    },
  };
}

function registerHelpers(hbs: typeof Handlebars): void {
  hbs.registerHelper('formatDate', (date: unknown, format?: unknown) => {
    if (!(date instanceof Date) || isNaN(date.getTime())) return '';
    if (format === 'iso') return date.toISOString();
    return date.toISOString().slice(0, 10); // YYYY-MM-DD
  });
  hbs.registerHelper('eq', (a: unknown, b: unknown) => a === b);
  hbs.registerHelper('json', (v: unknown) => JSON.stringify(v));
}
