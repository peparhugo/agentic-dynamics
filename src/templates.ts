import * as fs from 'fs';
import * as path from 'path';
import Handlebars from 'handlebars';

export const DEFAULT_TEMPLATE_NAME = 'page';
export const DEFAULT_LAYOUT_NAME = 'default';
export const INDEX_TEMPLATE_NAME = 'index';

const FALLBACK_LAYOUT = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{{title}}</title>
</head>
<body>
{{{body}}}
</body>
</html>
`;

const FALLBACK_PAGE_TEMPLATE = `<a href="index.html">&larr; Back to index</a>
<h1>{{title}}</h1>
{{#if date}}<p class="date">{{date}}</p>{{/if}}
{{#if tags.length}}<ul class="tags">{{#each tags}}<li>{{this}}</li>{{/each}}</ul>{{/if}}
<article>
{{{html}}}
</article>
`;

const FALLBACK_INDEX_TEMPLATE = `<h1>Index</h1>
<ul class="pages">
{{#each pages}}
<li><a href="{{outputPath}}">{{title}}</a>{{#if date}} <span class="date">{{date}}</span>{{/if}}</li>
{{/each}}
</ul>
`;

function readIfExists(filePath: string): string | null {
  return fs.existsSync(filePath) ? fs.readFileSync(filePath, 'utf-8') : null;
}

/**
 * Renders page content into a named template, then wraps the result in a
 * named layout via the layout's `{{{body}}}` placeholder. Templates and
 * layouts are read from disk on each render so authors can edit .hbs files
 * without restarting the build; falls back to built-in defaults whenever a
 * requested (or missing) template/layout file isn't present on disk, so a
 * project without a ./templates directory still builds.
 */
export class TemplateEngine {
  private readonly handlebars: typeof Handlebars;

  private readonly templatesDir: string;

  constructor(templatesDir: string) {
    this.templatesDir = templatesDir;
    this.handlebars = Handlebars.create();
    this.registerPartials();
  }

  private registerPartials(): void {
    const partialsDir = path.join(this.templatesDir, 'partials');
    if (!fs.existsSync(partialsDir)) return;

    const entries = fs.readdirSync(partialsDir).filter((name) => /\.hbs$/i.test(name));
    for (const entry of entries) {
      const name = entry.replace(/\.hbs$/i, '');
      const source = fs.readFileSync(path.join(partialsDir, entry), 'utf-8');
      this.handlebars.registerPartial(name, source);
    }
  }

  private fallbackFor(templateName: string): string {
    return templateName === INDEX_TEMPLATE_NAME ? FALLBACK_INDEX_TEMPLATE : FALLBACK_PAGE_TEMPLATE;
  }

  renderTemplate(templateName: string, context: Record<string, unknown>): string {
    const filePath = path.join(this.templatesDir, `${templateName}.hbs`);
    const source = readIfExists(filePath) ?? this.fallbackFor(templateName);
    return this.handlebars.compile(source)(context);
  }

  renderLayout(layoutName: string, context: Record<string, unknown>): string {
    const filePath = path.join(this.templatesDir, 'layouts', `${layoutName}.hbs`);
    const source = readIfExists(filePath) ?? FALLBACK_LAYOUT;
    return this.handlebars.compile(source)(context);
  }

  render(templateName: string, layoutName: string, context: Record<string, unknown>): string {
    const body = this.renderTemplate(templateName, context);
    return this.renderLayout(layoutName, { ...context, body });
  }
}
