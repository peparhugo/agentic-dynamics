import { readdir, readFile } from 'node:fs/promises';
import { extname, join, relative, sep } from 'node:path';
import Handlebars from 'handlebars';
import type { Page, Plugin, PluginContext } from '../plugin.js';

const defaultPageTemplate = `<article>
<h1>{{title}}</h1>
{{#if date}}<time datetime="{{date}}">{{date}}</time>{{/if}}
{{#if tags.length}}<p class="tags">{{#each tags}}<span>{{this}}</span> {{/each}}</p>{{/if}}
{{{html}}}
</article>`;

const defaultLayoutTemplate = `<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{{title}}</title></head>
<body>
<main>
<nav><a href="/index.html">Home</a></nav>
{{{body}}}
</main>
</body>
</html>
`;

function templateName(name: string): string {
  return name.endsWith('.hbs') ? name : `${name}.hbs`;
}

async function templateFiles(directory: string): Promise<string[]> {
  try {
    const entries = await readdir(directory, { withFileTypes: true });
    const files = await Promise.all(entries.map(async (entry) => {
      const filePath = join(directory, entry.name);
      if (entry.isDirectory()) return templateFiles(filePath);
      return extname(entry.name).toLowerCase() === '.hbs' ? [filePath] : [];
    }));
    return files.flat();
  } catch (error: unknown) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return [];
    throw error;
  }
}

export class TemplatePlugin implements Plugin {
  private renderPage?: (page: Page) => string;

  async onStart({ templatesDirectory }: PluginContext): Promise<void> {
    const handlebars = Handlebars.create();
    const files = await templateFiles(templatesDirectory);
    const templates = new Map<string, string>();
    await Promise.all(files.map(async (filePath) => {
      templates.set(relative(templatesDirectory, filePath).split(sep).join('/'), await readFile(filePath, 'utf8'));
    }));
    for (const [name, source] of templates) {
      if (name.startsWith('partials/')) handlebars.registerPartial(name.slice('partials/'.length, -'.hbs'.length), source);
    }
    const render = (name: string | undefined, fallback: string, context: Record<string, unknown>, directory = ''): string => {
      const requested = directory + templateName(name ?? 'default');
      const source = templates.get(requested) ?? (name ? undefined : templates.get(`${directory}default.hbs`)) ?? fallback;
      if (!source) throw new Error(`Template not found: ${requested}`);
      return handlebars.compile(source)(context);
    };
    this.renderPage = (page) => {
      const context = { ...page.data, ...page };
      const body = render(page.template, defaultPageTemplate, context);
      return page.layout === false ? body : render(page.layout, defaultLayoutTemplate, { ...context, body: new handlebars.SafeString(body) }, 'layouts/');
    };
  }

  onFile(page: Page, context: PluginContext): void {
    if (!this.renderPage) throw new Error('Template plugin has not started');
    context.html = this.renderPage(page);
  }
}
