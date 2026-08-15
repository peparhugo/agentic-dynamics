import fs from 'fs';
import path from 'path';
import Handlebars from 'handlebars';
import matter from 'gray-matter';

const TEMPLATE_EXTENSIONS = ['.hbs', '.handlebars'];

const DEFAULT_TEMPLATE = 'default';
const DEFAULT_LAYOUT = 'default';

export interface TemplateContext {
  title: string;
  date?: string;
  tags: string[];
  slug: string;
  body: string;
  content: string;
  [key: string]: unknown;
}

export interface TemplateEngineOptions {
  templatesDir: string;
}

interface ParsedTemplate {
  content: string;
  data: Record<string, unknown>;
}

/**
 * Handlebars-based template engine.
 *
 * Layouts are full HTML documents under `templates/layouts/` that receive the
 * rendered page in a `{{{body}}}` placeholder. Page templates under
 * `templates/` (selected via the `template` frontmatter key, defaulting to
 * `default`) can wrap the Markdown output and may declare their own `layout`
 * through a YAML frontmatter block. Partials under `templates/partials/` are
 * registered as `{{> name }}`.
 */
export class TemplateEngine {
  private readonly templatesDir: string;
  private readonly layoutsDir: string;
  private readonly partialsDir: string;
  private readonly hbs: typeof Handlebars;

  constructor(options: TemplateEngineOptions) {
    this.templatesDir = options.templatesDir;
    this.layoutsDir = path.join(this.templatesDir, 'layouts');
    this.partialsDir = path.join(this.templatesDir, 'partials');
    this.hbs = Handlebars.create();
    this.registerPartials();
  }

  /** Whether a templates directory exists and should be used. */
  hasTemplatesDir(): boolean {
    return fs.existsSync(this.templatesDir);
  }

  /**
   * Render a page through an optional page template and an optional layout.
   * When neither a matching template nor layout file exists, the raw body is
   * returned unchanged.
   */
  render(templateName: string | undefined, layoutName: string | undefined, context: TemplateContext): string {
    let body = context.body;
    let layout = layoutName;

    const templateFile = this.findTemplate(templateName ?? DEFAULT_TEMPLATE);
    if (templateFile) {
      const parsed = this.readFile(templateFile);
      body = this.hbs.compile(parsed.content)(context);
      if (layout === undefined && typeof parsed.data.layout === 'string' && parsed.data.layout) {
        layout = parsed.data.layout;
      }
    }

    const layoutFile = this.findLayout(layout ?? DEFAULT_LAYOUT);
    if (!layoutFile) return body;

    const parsed = this.readFile(layoutFile);
    return this.hbs.compile(parsed.content)({ ...context, body, content: body });
  }

  private registerPartials(): void {
    if (!fs.existsSync(this.partialsDir)) return;

    for (const entry of fs.readdirSync(this.partialsDir).sort()) {
      const ext = path.extname(entry).toLowerCase();
      if (!TEMPLATE_EXTENSIONS.includes(ext)) continue;
      const name = path.basename(entry, ext);
      const source = fs.readFileSync(path.join(this.partialsDir, entry), 'utf-8');
      this.hbs.registerPartial(name, source);
    }
  }

  private findTemplate(name: string): string | undefined {
    return this.findFile(this.templatesDir, name);
  }

  private findLayout(name: string): string | undefined {
    return this.findFile(this.layoutsDir, name);
  }

  private findFile(dir: string, name: string): string | undefined {
    const direct = path.join(dir, name);
    if (fs.existsSync(direct) && fs.statSync(direct).isFile()) return direct;

    for (const ext of TEMPLATE_EXTENSIONS) {
      const candidate = path.join(dir, `${name}${ext}`);
      if (fs.existsSync(candidate)) return candidate;
    }

    return undefined;
  }

  private readFile(file: string): ParsedTemplate {
    const raw = fs.readFileSync(file, 'utf-8');
    const parsed = matter(raw);
    return { content: parsed.content, data: parsed.data as Record<string, unknown> };
  }
}
