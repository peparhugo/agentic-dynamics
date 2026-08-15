import fs from 'fs';
import path from 'path';
import Handlebars from 'handlebars';

export interface PageContext {
  title: string;
  date?: string;
  tags: string[];
  slug: string;
  content: string;
  body: string;
  [key: string]: unknown;
}

const LAYOUTS_DIR = 'layouts';
const PARTIALS_DIR = 'partials';
const DEFAULT_LAYOUT = 'default';

function listTemplateFiles(dir: string): string[] {
  const files: string[] = [];
  if (!fs.existsSync(dir)) {
    return files;
  }
  for (const entry of fs.readdirSync(dir)) {
    const fullPath = path.join(dir, entry);
    const stat = fs.statSync(fullPath);
    if (stat.isDirectory()) {
      files.push(...listTemplateFiles(fullPath));
    } else if (stat.isFile() && /\.hbs$/i.test(entry)) {
      files.push(fullPath);
    }
  }
  return files;
}

function templateName(filePath: string, rootDir: string): string {
  const relative = path.relative(rootDir, filePath);
  const withoutExtension = relative.replace(/\.hbs$/i, '');
  return withoutExtension.split(path.sep).join('/');
}

function normalizeTemplateName(name: string): string {
  let normalized = name.trim();
  normalized = normalized.replace(/^\.?\//, '');
  normalized = normalized.replace(/^layouts\//, '');
  normalized = normalized.replace(/\.hbs$/i, '');
  return normalized.split(/[\\/]/).join('/');
}

/**
 * A Handlebars-based template engine scoped to a single `templates` directory.
 *
 * It discovers layout templates from `templates/layouts/*.hbs` and reusable
 * partials from `templates/partials/*.hbs`. Each instance uses its own
 * isolated Handlebars environment so multiple builds never leak state.
 */
export class TemplateEngine {
  private hbs: typeof Handlebars;
  private layouts: Map<string, Handlebars.TemplateDelegate>;
  private defaultLayout: string;

  constructor(private templatesDir: string) {
    this.hbs = Handlebars.create();
    this.layouts = new Map();
    this.defaultLayout = DEFAULT_LAYOUT;

    this.registerPartials();
    this.registerLayouts();
  }

  private registerPartials(): void {
    const partialsDir = path.join(this.templatesDir, PARTIALS_DIR);
    for (const file of listTemplateFiles(partialsDir)) {
      const name = templateName(file, partialsDir);
      this.hbs.registerPartial(name, fs.readFileSync(file, 'utf-8'));
    }
  }

  private registerLayouts(): void {
    const layoutsDir = path.join(this.templatesDir, LAYOUTS_DIR);
    for (const file of listTemplateFiles(layoutsDir)) {
      const name = templateName(file, layoutsDir);
      this.layouts.set(name, this.hbs.compile(fs.readFileSync(file, 'utf-8')));
    }
  }

  get availableLayouts(): string[] {
    return Array.from(this.layouts.keys());
  }

  hasLayout(name: string): boolean {
    return this.layouts.has(normalizeTemplateName(name));
  }

  /**
   * Render a page using the requested layout (falling back to the default
   * layout). Returns `null` when no matching layout exists so the caller can
   * fall back to its built-in HTML rendering.
   */
  render(templateName: string | undefined, context: PageContext): string | null {
    const candidates: string[] = [];
    if (templateName) {
      candidates.push(normalizeTemplateName(templateName));
    }
    candidates.push(this.defaultLayout);

    for (const name of candidates) {
      const layout = this.layouts.get(name);
      if (layout) {
        return layout(context);
      }
    }
    return null;
  }
}
