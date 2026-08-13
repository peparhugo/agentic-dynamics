import * as fs from 'fs';
import * as path from 'path';
import Handlebars from 'handlebars';

export function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function readFile(filePath: string): string | undefined {
  return fs.existsSync(filePath) ? fs.readFileSync(filePath, 'utf-8') : undefined;
}

/**
 * Thin wrapper around Handlebars for page templates, layouts, and partials.
 * Callers pre-escape untrusted values with escapeHtml before handing them in as
 * context, so templates always use triple-stache `{{{ }}}` — Handlebars is used
 * purely for structure (loops, includes, layout composition), not escaping.
 */
export class TemplateEngine {
  private handlebars: typeof Handlebars;
  private templatesDir: string;
  private templateCache = new Map<string, HandlebarsTemplateDelegate>();
  private layoutCache = new Map<string, HandlebarsTemplateDelegate>();

  constructor(templatesDir: string) {
    this.templatesDir = templatesDir;
    this.handlebars = Handlebars.create();
    this.registerPartials();
  }

  private registerPartials(): void {
    const partialsDir = path.join(this.templatesDir, 'partials');
    if (!fs.existsSync(partialsDir)) return;
    for (const file of fs.readdirSync(partialsDir)) {
      if (!file.endsWith('.hbs')) continue;
      const name = file.replace(/\.hbs$/, '');
      const source = fs.readFileSync(path.join(partialsDir, file), 'utf-8');
      this.handlebars.registerPartial(name, source);
    }
  }

  private compile(
    cache: Map<string, HandlebarsTemplateDelegate>,
    filePath: string,
    kind: string
  ): HandlebarsTemplateDelegate {
    const cached = cache.get(filePath);
    if (cached) return cached;
    const source = readFile(filePath);
    if (source === undefined) {
      throw new Error(`${kind} not found: ${filePath}`);
    }
    const compiled = this.handlebars.compile(source);
    cache.set(filePath, compiled);
    return compiled;
  }

  private compileTemplate(name: string): HandlebarsTemplateDelegate {
    return this.compile(this.templateCache, path.join(this.templatesDir, `${name}.hbs`), 'Template');
  }

  private compileLayout(name: string): HandlebarsTemplateDelegate {
    return this.compile(this.layoutCache, path.join(this.templatesDir, 'layouts', `${name}.hbs`), 'Layout');
  }

  /** Renders `templateName` to produce the page body, then wraps it in `layoutName` via {{{body}}}. */
  render(
    templateName: string,
    layoutName: string,
    templateContext: Record<string, unknown>,
    layoutContext: Record<string, unknown>
  ): string {
    const body = this.compileTemplate(templateName)(templateContext);
    return this.compileLayout(layoutName)({ ...layoutContext, body });
  }
}
