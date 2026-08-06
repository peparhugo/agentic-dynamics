import Handlebars from 'handlebars';
import fs from 'node:fs';
import path from 'node:path';

export interface TemplateEngine {
  /** Render the named layout ("default", "post", ...) with the given context. */
  render(layout: string, context: Record<string, unknown>): string;
  hasLayout(layout: string): boolean;
  layouts(): string[];
}

function formatDate(date: unknown, format?: unknown): string {
  const d = date instanceof Date ? date : new Date(String(date));
  if (isNaN(d.getTime())) return '';
  if (typeof format === 'string' && format === 'iso') return d.toISOString();
  return d.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    timeZone: 'UTC',
  });
}

function registerHelpers(hb: typeof Handlebars): void {
  hb.registerHelper('formatDate', (date: unknown, format: unknown) =>
    formatDate(date, typeof format === 'string' ? format : undefined),
  );
  hb.registerHelper('slugifyTag', (tag: unknown) =>
    String(tag)
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, ''),
  );
  hb.registerHelper('eq', (a: unknown, b: unknown) => a === b);
  hb.registerHelper('limit', (arr: unknown, n: unknown) =>
    Array.isArray(arr) ? arr.slice(0, Number(n)) : [],
  );
}

/**
 * Create a template engine from a directory of Handlebars templates.
 *
 * Layout resolution:
 *   <templateDir>/*.hbs           -> layouts, addressable by basename
 *   <templateDir>/partials/*.hbs  -> registered as partials by basename
 */
export function createTemplateEngine(templateDir: string): TemplateEngine {
  const hb = Handlebars.create();
  registerHelpers(hb);

  const compiled = new Map<string, Handlebars.TemplateDelegate>();

  if (!fs.existsSync(templateDir)) {
    throw new Error(`Template directory not found: ${templateDir}`);
  }

  for (const entry of fs.readdirSync(templateDir, { withFileTypes: true })) {
    if (entry.isFile() && entry.name.endsWith('.hbs')) {
      const name = path.basename(entry.name, '.hbs');
      const src = fs.readFileSync(path.join(templateDir, entry.name), 'utf8');
      compiled.set(name, hb.compile(src));
    }
  }

  const partialsDir = path.join(templateDir, 'partials');
  if (fs.existsSync(partialsDir)) {
    for (const entry of fs.readdirSync(partialsDir, { withFileTypes: true })) {
      if (entry.isFile() && entry.name.endsWith('.hbs')) {
        const name = path.basename(entry.name, '.hbs');
        hb.registerPartial(name, fs.readFileSync(path.join(partialsDir, entry.name), 'utf8'));
      }
    }
  }

  if (!compiled.has('default')) {
    throw new Error(`Template directory must contain a "default.hbs" layout: ${templateDir}`);
  }

  return {
    render(layout: string, context: Record<string, unknown>): string {
      const template = compiled.get(layout) ?? compiled.get('default')!;
      return template(context);
    },
    hasLayout: (layout: string) => compiled.has(layout),
    layouts: () => [...compiled.keys()],
  };
}
