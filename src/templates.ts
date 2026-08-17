import fs from 'fs';
import path from 'path';
import Handlebars from 'handlebars';

export const DEFAULT_TEMPLATE_NAME = 'default';
export const DEFAULT_LAYOUT_NAME = 'default';

export const DEFAULT_TEMPLATE_SOURCE = '{{{body}}}';

export const DEFAULT_LAYOUT_SOURCE = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{{title}}</title>
</head>
<body>
<h1>{{title}}</h1>
{{#if date}}<p class="date">{{date}}</p>{{/if}}
{{#if tags}}<ul class="tags">{{#each tags}}<li>{{this}}</li>{{/each}}</ul>{{/if}}
<div class="content">
{{{body}}}
</div>
</body>
</html>
`;

const TEMPLATE_EXTENSIONS = ['.hbs', '.handlebars'];

/**
 * Resolve a template/layout/partial name to a file path within `dir`. Names
 * may include an extension or omit it (in which case `.hbs`/`.handlebars` are
 * tried). Returns null when no matching file exists.
 */
export function resolveFile(dir: string, name: string): string | null {
  const candidates: string[] = [];
  if (path.extname(name)) {
    candidates.push(name);
  } else {
    for (const ext of TEMPLATE_EXTENSIONS) {
      candidates.push(name + ext);
    }
  }
  for (const candidate of candidates) {
    const full = path.join(dir, candidate);
    if (fs.existsSync(full) && fs.statSync(full).isFile()) {
      return full;
    }
  }
  return null;
}

export function resolveTemplateFile(
  templatesDir: string,
  name: string | undefined,
  defaultName: string
): string | null {
  const resolved = name && name.length > 0 ? name : defaultName;
  return resolveFile(templatesDir, resolved);
}

export function resolveLayoutFile(
  layoutsDir: string,
  name: string | undefined,
  defaultName: string
): string | null {
  const resolved = name && name.length > 0 ? name : defaultName;
  return resolveFile(layoutsDir, resolved);
}

export function listPartialFiles(partialsDir: string): string[] {
  if (!fs.existsSync(partialsDir)) {
    return [];
  }
  return fs
    .readdirSync(partialsDir, { withFileTypes: true })
    .filter((entry) => entry.isFile() && TEMPLATE_EXTENSIONS.includes(path.extname(entry.name)))
    .map((entry) => path.join(partialsDir, entry.name));
}

export interface TemplateEngineOptions {
  defaultTemplate?: string;
  defaultLayout?: string;
}

export interface RenderContext {
  [key: string]: unknown;
}

export class TemplateEngine {
  private readonly handlebars: typeof Handlebars;
  private readonly templatesDir: string;
  private readonly layoutsDir: string;
  private readonly partialsDir: string;
  private readonly defaultTemplate: string;
  private readonly defaultLayout: string;
  private readonly compiled: Map<string, Handlebars.TemplateDelegate>;

  constructor(templatesDir: string, options: TemplateEngineOptions = {}) {
    this.templatesDir = path.resolve(templatesDir);
    this.layoutsDir = path.join(this.templatesDir, 'layouts');
    this.partialsDir = path.join(this.templatesDir, 'partials');
    this.defaultTemplate = options.defaultTemplate ?? DEFAULT_TEMPLATE_NAME;
    this.defaultLayout = options.defaultLayout ?? DEFAULT_LAYOUT_NAME;
    this.handlebars = Handlebars.create();
    this.compiled = new Map();
    this.registerPartials();
  }

  /**
   * Render a page: apply the page template (produces the body) and then wrap
   * the result with the layout template via the {{{body}}} placeholder.
   */
  render(
    templateName: string | undefined,
    layoutName: string | false | undefined,
    context: RenderContext
  ): string {
    const templateSource = this.resolveTemplate(templateName);
    const body = this.compile(templateSource)({
      ...context,
      body: context.content,
    });

    if (layoutName === false) {
      return body;
    }

    const layoutSource = this.resolveLayout(layoutName);
    return this.compile(layoutSource)({ ...context, body });
  }

  private resolveTemplate(name: string | undefined): string {
    const file = resolveTemplateFile(this.templatesDir, name, this.defaultTemplate);
    if (file) {
      return fs.readFileSync(file, 'utf8');
    }
    return DEFAULT_TEMPLATE_SOURCE;
  }

  private resolveLayout(name: string | undefined): string {
    const file = resolveLayoutFile(this.layoutsDir, name, this.defaultLayout);
    if (file) {
      return fs.readFileSync(file, 'utf8');
    }
    return DEFAULT_LAYOUT_SOURCE;
  }

  private compile(source: string): Handlebars.TemplateDelegate {
    const cached = this.compiled.get(source);
    if (cached) {
      return cached;
    }
    const fn = this.handlebars.compile(source);
    this.compiled.set(source, fn);
    return fn;
  }

  private registerPartials(): void {
    for (const file of listPartialFiles(this.partialsDir)) {
      const ext = path.extname(file);
      const name = path.basename(file, ext);
      const source = fs.readFileSync(file, 'utf8');
      this.handlebars.registerPartial(name, source);
    }
  }
}
