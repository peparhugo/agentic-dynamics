import * as fs from 'fs';
import * as path from 'path';
import Handlebars from 'handlebars';

export const DEFAULT_LAYOUT_NAME = 'default';

export interface RenderContext {
  title: string;
  date?: string;
  tags: string[];
  body: string;
}

/**
 * Compiles Handlebars layout templates and registers partials, so pages can
 * be wrapped in a layout selected via frontmatter (falling back to the
 * `default` layout when none is specified).
 */
export class TemplateEngine {
  private readonly handlebars: typeof Handlebars;
  private readonly layouts = new Map<string, HandlebarsTemplateDelegate>();

  constructor(private readonly templatesDir: string) {
    this.handlebars = Handlebars.create();

    if (!fs.existsSync(templatesDir) || !fs.statSync(templatesDir).isDirectory()) {
      throw new Error(`Templates directory not found: ${templatesDir}`);
    }

    this.registerPartials();
    this.loadLayouts();

    if (!this.layouts.has(DEFAULT_LAYOUT_NAME)) {
      throw new Error(
        `Default layout "${DEFAULT_LAYOUT_NAME}.hbs" not found in ${this.layoutsDir}`
      );
    }
  }

  private get partialsDir(): string {
    return path.join(this.templatesDir, 'partials');
  }

  private get layoutsDir(): string {
    return path.join(this.templatesDir, 'layouts');
  }

  private registerPartials(): void {
    if (!fs.existsSync(this.partialsDir)) return;

    for (const file of listTemplateFiles(this.partialsDir)) {
      const name = path.basename(file, '.hbs');
      const source = fs.readFileSync(path.join(this.partialsDir, file), 'utf8');
      this.handlebars.registerPartial(name, source);
    }
  }

  private loadLayouts(): void {
    if (!fs.existsSync(this.layoutsDir)) {
      throw new Error(`Layouts directory not found: ${this.layoutsDir}`);
    }

    for (const file of listTemplateFiles(this.layoutsDir)) {
      const name = path.basename(file, '.hbs');
      const source = fs.readFileSync(path.join(this.layoutsDir, file), 'utf8');
      this.layouts.set(name, this.handlebars.compile(source));
    }
  }

  hasLayout(name: string): boolean {
    return this.layouts.has(name);
  }

  render(layoutName: string | undefined, context: RenderContext): string {
    const name = layoutName && layoutName.trim() ? layoutName.trim() : DEFAULT_LAYOUT_NAME;
    const layout = this.layouts.get(name);

    if (!layout) {
      throw new Error(`Template layout "${name}" not found in ${this.layoutsDir}`);
    }

    return layout(context);
  }
}

function listTemplateFiles(dir: string): string[] {
  return fs
    .readdirSync(dir, { withFileTypes: true })
    .filter((entry) => entry.isFile() && /\.hbs$/i.test(entry.name))
    .map((entry) => entry.name);
}
