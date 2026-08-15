import fs from 'fs';
import path from 'path';
import Handlebars from 'handlebars';
import { Page } from './types';

export const DEFAULT_LAYOUT_NAME = 'default';

export interface PageTemplateData {
  title: string;
  date?: string;
  tags: string[];
  body: string;
}

const FALLBACK_LAYOUT = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{{title}}</title>
</head>
<body>
<article>
<h1>{{title}}</h1>
{{#if date}}<p class="date">{{date}}</p>
{{/if}}{{#if tags.length}}<ul class="tags">{{#each tags}}<li>{{this}}</li>{{/each}}</ul>
{{/if}}{{{body}}}
</article>
</body>
</html>
`;

const FALLBACK_INDEX = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Index</title>
</head>
<body>
<h1>All Pages</h1>
<ul class="page-list">
{{#each pages}}
<li><a href="{{outputPath}}">{{title}}</a>{{#if date}} <span class="date">{{date}}</span>{{/if}}</li>
{{/each}}
</ul>
</body>
</html>
`;

/**
 * Compiles page and index templates for a single ./templates directory.
 * Falls back to built-in Handlebars templates when the project has no
 * templates directory (or is missing the default layout/index template),
 * so `ssg build` keeps working without any project scaffolding.
 */
export class TemplateEngine {
  private readonly layoutsDir: string;
  private readonly partialsDir: string;
  private readonly indexTemplatePath: string;
  private readonly handlebars: typeof Handlebars;
  private readonly layoutCache = new Map<string, HandlebarsTemplateDelegate>();
  private indexTemplate?: HandlebarsTemplateDelegate;
  private partialsRegistered = false;

  constructor(templatesDir: string) {
    this.layoutsDir = path.join(templatesDir, 'layouts');
    this.partialsDir = path.join(templatesDir, 'partials');
    this.indexTemplatePath = path.join(templatesDir, 'index.hbs');
    this.handlebars = Handlebars.create();
  }

  private registerPartials(): void {
    if (this.partialsRegistered) return;
    this.partialsRegistered = true;
    if (!fs.existsSync(this.partialsDir)) return;
    for (const file of fs.readdirSync(this.partialsDir)) {
      if (!file.toLowerCase().endsWith('.hbs')) continue;
      const name = file.replace(/\.hbs$/i, '');
      const source = fs.readFileSync(path.join(this.partialsDir, file), 'utf-8');
      this.handlebars.registerPartial(name, source);
    }
  }

  private loadLayout(name: string): HandlebarsTemplateDelegate {
    this.registerPartials();
    const cached = this.layoutCache.get(name);
    if (cached) return cached;

    const layoutPath = path.join(this.layoutsDir, `${name}.hbs`);
    let source: string;
    if (fs.existsSync(layoutPath)) {
      source = fs.readFileSync(layoutPath, 'utf-8');
    } else if (name === DEFAULT_LAYOUT_NAME) {
      source = FALLBACK_LAYOUT;
    } else {
      throw new Error(`Unknown template "${name}": no layout found at ${layoutPath}`);
    }

    const compiled = this.handlebars.compile(source);
    this.layoutCache.set(name, compiled);
    return compiled;
  }

  renderPage(data: PageTemplateData, templateName?: string): string {
    const name = templateName && templateName.trim().length > 0 ? templateName.trim() : DEFAULT_LAYOUT_NAME;
    const layout = this.loadLayout(name);
    return layout({
      title: data.title,
      date: data.date,
      tags: data.tags,
      body: data.body,
    });
  }

  renderIndex(pages: Page[]): string {
    this.registerPartials();
    if (!this.indexTemplate) {
      const source = fs.existsSync(this.indexTemplatePath)
        ? fs.readFileSync(this.indexTemplatePath, 'utf-8')
        : FALLBACK_INDEX;
      this.indexTemplate = this.handlebars.compile(source);
    }
    return this.indexTemplate({ pages });
  }
}

const engineCache = new Map<string, TemplateEngine>();

export function getTemplateEngine(templatesDir: string): TemplateEngine {
  let engine = engineCache.get(templatesDir);
  if (!engine) {
    engine = new TemplateEngine(templatesDir);
    engineCache.set(templatesDir, engine);
  }
  return engine;
}

/**
 * Drops cached TemplateEngine instances so the next getTemplateEngine() call
 * recompiles layouts/partials from disk. Needed by long-lived processes (like
 * the dev server) that rebuild after a template file changes; a one-shot
 * `ssg build` never needs this since it exits after a single build.
 */
export function clearTemplateEngineCache(templatesDir?: string): void {
  if (templatesDir) {
    engineCache.delete(templatesDir);
  } else {
    engineCache.clear();
  }
}
