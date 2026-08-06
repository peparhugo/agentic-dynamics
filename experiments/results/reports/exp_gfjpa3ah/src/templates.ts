import Handlebars from 'handlebars';
import { promises as fs } from 'node:fs';
import path from 'node:path';

export interface TemplateEngine {
  /** Render the named layout (without .hbs extension) with the given context. */
  render(layout: string, context: Record<string, unknown>): string;
  hasLayout(layout: string): boolean;
}

/**
 * Template directory convention:
 *   templates/layouts/*.hbs   -> layouts, selected via frontmatter `layout` (default: "default")
 *   templates/partials/*.hbs  -> partials, referenced as {{> name}}
 *
 * Layouts may themselves declare a parent via `{{!< parent}}` on the first line;
 * the child's output is provided to the parent as `{{{body}}}`.
 */
export async function createTemplateEngine(templateDir: string): Promise<TemplateEngine> {
  const hb = Handlebars.create();
  registerHelpers(hb);

  const layoutSources = await readTemplates(path.join(templateDir, 'layouts'));
  const partialSources = await readTemplates(path.join(templateDir, 'partials'));

  if (!layoutSources.has('default')) {
    throw new Error(`Missing required layout: ${path.join(templateDir, 'layouts', 'default.hbs')}`);
  }

  for (const [name, source] of partialSources) {
    hb.registerPartial(name, source);
  }

  const layouts = new Map<string, { template: Handlebars.TemplateDelegate; parent: string | null }>();
  for (const [name, source] of layoutSources) {
    const { parent, body } = extractParent(source);
    layouts.set(name, { template: hb.compile(body), parent });
  }

  function render(layout: string, context: Record<string, unknown>): string {
    let current = layouts.get(layout);
    if (!current) current = layouts.get('default')!;
    let output = current.template(context);
    const visited = new Set<string>([layout]);
    while (current.parent) {
      const parentName: string = current.parent;
      if (visited.has(parentName)) throw new Error(`Circular layout inheritance involving "${parentName}"`);
      visited.add(parentName);
      const parent = layouts.get(parentName);
      if (!parent) throw new Error(`Layout "${parentName}" (parent of another layout) not found`);
      output = parent.template({ ...context, body: new Handlebars.SafeString(output) });
      current = parent;
    }
    return output;
  }

  return { render, hasLayout: (l) => layouts.has(l) };
}

function extractParent(source: string): { parent: string | null; body: string } {
  const match = source.match(/^\{\{!<\s*([\w-]+)\s*\}\}\r?\n?/);
  if (match) return { parent: match[1], body: source.slice(match[0].length) };
  return { parent: null, body: source };
}

async function readTemplates(dir: string): Promise<Map<string, string>> {
  const out = new Map<string, string>();
  let entries: string[];
  try {
    entries = await fs.readdir(dir);
  } catch {
    return out; // directory may not exist (e.g. no partials)
  }
  for (const entry of entries) {
    if (!entry.endsWith('.hbs')) continue;
    const source = await fs.readFile(path.join(dir, entry), 'utf8');
    out.set(entry.replace(/\.hbs$/, ''), source);
  }
  return out;
}

export function registerHelpers(hb: typeof Handlebars): void {
  hb.registerHelper('formatDate', (date: unknown, format?: unknown) => {
    if (!(date instanceof Date) || isNaN(date.getTime())) return '';
    const fmt = typeof format === 'string' ? format : 'YYYY-MM-DD';
    const pad = (n: number) => String(n).padStart(2, '0');
    const months = [
      'January', 'February', 'March', 'April', 'May', 'June',
      'July', 'August', 'September', 'October', 'November', 'December',
    ];
    return fmt
      .replace(/YYYY/g, String(date.getUTCFullYear()))
      .replace(/MMMM/g, months[date.getUTCMonth()])
      .replace(/MM/g, pad(date.getUTCMonth() + 1))
      .replace(/DD/g, pad(date.getUTCDate()));
  });
  hb.registerHelper('isoDate', (date: unknown) =>
    date instanceof Date && !isNaN(date.getTime()) ? date.toISOString() : '',
  );
  hb.registerHelper('limit', (arr: unknown, n: unknown) =>
    Array.isArray(arr) ? arr.slice(0, Number(n) || 0) : [],
  );
  hb.registerHelper('eq', (a: unknown, b: unknown) => a === b);
  hb.registerHelper('join', (arr: unknown, sep: unknown) =>
    Array.isArray(arr) ? arr.join(typeof sep === 'string' ? sep : ', ') : '',
  );
}
