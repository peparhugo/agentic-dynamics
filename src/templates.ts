import * as fs from 'fs';
import * as path from 'path';
import Handlebars from 'handlebars';

export interface RenderContext {
  [key: string]: unknown;
}

export const DEFAULT_TEMPLATE_NAME = 'default';
export const DEFAULT_LAYOUT_NAME = 'default';

const BUILTIN_DEFAULT_TEMPLATE = `<article>
<h1>{{title}}</h1>
{{{meta}}}
<div class="content">
{{{content}}}
</div>
</article>
`;

const BUILTIN_DEFAULT_LAYOUT = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{title}}</title>
</head>
<body>
<header><a href="{{home}}">Home</a></header>
{{{body}}}
</body>
</html>
`;

type TemplateDelegate = Handlebars.TemplateDelegate;

function collectHbsFiles(dir: string): string[] {
  const results: string[] = [];
  if (!fs.existsSync(dir)) {
    return results;
  }
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      results.push(...collectHbsFiles(full));
    } else if (entry.isFile() && entry.name.toLowerCase().endsWith('.hbs')) {
      results.push(full);
    }
  }
  return results;
}

function resolveNamedFile(name: string, baseDir: string): string | null {
  if (typeof name !== 'string' || name.trim().length === 0) {
    return null;
  }
  const candidates = name.toLowerCase().endsWith('.hbs')
    ? [name]
    : [`${name}.hbs`, name];
  for (const candidate of candidates) {
    const full = path.join(baseDir, candidate);
    if (fs.existsSync(full) && fs.statSync(full).isFile()) {
      return full;
    }
  }
  return null;
}

function partialName(partialsDir: string, file: string): string {
  const rel = path.relative(partialsDir, file);
  const withoutExt = rel.toLowerCase().endsWith('.hbs')
    ? rel.slice(0, -'.hbs'.length)
    : rel;
  return withoutExt.split(path.sep).join('/');
}

export class TemplateEngine {
  private readonly hbs: typeof Handlebars;
  private readonly templatesDir: string;
  private readonly templates = new Map<string, TemplateDelegate>();
  private readonly layouts = new Map<string, TemplateDelegate>();

  constructor(templatesDir: string) {
    this.templatesDir = templatesDir;
    this.hbs = Handlebars.create();
    this.registerPartials();
  }

  private registerPartials(): void {
    const partialsDir = path.join(this.templatesDir, 'partials');
    for (const file of collectHbsFiles(partialsDir)) {
      const name = partialName(partialsDir, file);
      const source = fs.readFileSync(file, 'utf8');
      this.hbs.registerPartial(name, this.hbs.compile(source));
    }
  }

  private resolveTemplateFile(name: string): string | null {
    return resolveNamedFile(name, this.templatesDir);
  }

  private resolveLayoutFile(name: string): string | null {
    return resolveNamedFile(name, path.join(this.templatesDir, 'layouts'));
  }

  private loadTemplate(name: string): TemplateDelegate {
    const cached = this.templates.get(name);
    if (cached) {
      return cached;
    }

    const file = this.resolveTemplateFile(name);
    let source: string | null = null;
    if (file) {
      source = fs.readFileSync(file, 'utf8');
    } else if (name === DEFAULT_TEMPLATE_NAME) {
      source = BUILTIN_DEFAULT_TEMPLATE;
    }

    if (source === null) {
      throw new Error(`Template not found: ${name}`);
    }

    const compiled = this.hbs.compile(source);
    this.templates.set(name, compiled);
    return compiled;
  }

  private loadLayout(name: string): TemplateDelegate {
    const cached = this.layouts.get(name);
    if (cached) {
      return cached;
    }

    const file = this.resolveLayoutFile(name);
    let source: string | null = null;
    if (file) {
      source = fs.readFileSync(file, 'utf8');
    } else if (name === DEFAULT_LAYOUT_NAME) {
      source = BUILTIN_DEFAULT_LAYOUT;
    }

    if (source === null) {
      throw new Error(`Layout not found: ${name}`);
    }

    const compiled = this.hbs.compile(source);
    this.layouts.set(name, compiled);
    return compiled;
  }

  render(
    templateName: string | null,
    layoutName: string | null,
    context: RenderContext
  ): string {
    const template = this.loadTemplate(templateName ?? DEFAULT_TEMPLATE_NAME);
    const body = template(context);

    const layout = this.loadLayout(layoutName ?? DEFAULT_LAYOUT_NAME);
    return layout({ ...context, body });
  }
}
