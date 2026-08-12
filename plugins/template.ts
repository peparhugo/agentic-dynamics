import fs from 'node:fs';
import path from 'node:path';
import Handlebars from 'handlebars';
import type { Page } from '../src/generator';
import type { BuildContext, Plugin } from '../src/plugin';

function document(title: string, body: string): string {
  return `<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n<title>${title}</title>\n</head>\n<body>\n${body}\n</body>\n</html>\n`;
}

function templateFile(directory: string, name: string, subdirectory = ''): string | undefined {
  const requested = path.extname(name) ? name : `${name}.hbs`;
  const filename = path.join(directory, subdirectory, requested);
  return fs.existsSync(filename) ? filename : undefined;
}

export class TemplatePlugin implements Plugin {
  private renderer(directory: string) {
    const handlebars = Handlebars.create();
    const partialsDir = path.join(directory, 'partials');
    if (fs.existsSync(partialsDir)) for (const filename of fs.readdirSync(partialsDir)) {
      if (/\.hbs$/i.test(filename)) handlebars.registerPartial(filename.replace(/\.hbs$/i, ''), fs.readFileSync(path.join(partialsDir, filename), 'utf8'));
    }
    return {
      render: (name: string, context: Record<string, unknown>) => {
        const filename = templateFile(directory, name);
        return filename ? handlebars.compile(fs.readFileSync(filename, 'utf8'))(context) : undefined;
      },
      renderFile: (filename: string, context: Record<string, unknown>) => handlebars.compile(fs.readFileSync(filename, 'utf8'))(context)
    };
  }

  private withLayout(context: Record<string, unknown>, directory: string, rendered: string, renderer: ReturnType<TemplatePlugin['renderer']>): string {
    const layoutName = typeof context.layout === 'string' ? context.layout : templateFile(directory, 'default', 'layouts') ? 'default' : undefined;
    if (!layoutName) return rendered;
    const layout = templateFile(directory, layoutName, 'layouts');
    if (!layout) throw new Error(`Layout template not found: ${layoutName}`);
    return renderer.renderFile(layout, { ...context, body: rendered });
  }

  onFile(page: Page, context: BuildContext): Page {
    const directory = context.options.templatesDir;
    const renderer = this.renderer(directory);
    const templateName = page.template ?? (templateFile(directory, 'page') ? 'page' : 'default');
    const templateContext = { ...page, content: page.html, page } as Record<string, unknown>;
    const tags = page.tags.length ? `<p class="tags">Tags: ${page.tags.join(', ')}</p>\n` : '';
    const body = `<article>\n<h1>${page.title}</h1>\n${tags}${page.html}\n</article>`;
    const rendered = renderer.render(templateName, templateContext) ?? document(page.title, body);
    const output = this.withLayout(templateContext, directory, rendered, renderer);
    const target = path.join(context.options.outputDir, `${page.slug}.html`);
    fs.mkdirSync(path.dirname(target), { recursive: true });
    fs.writeFileSync(target, output);
    return page;
  }

  afterBuild(context: BuildContext): void {
    const renderer = this.renderer(context.options.templatesDir);
    const templateContext = { pages: context.pages, title: 'Index' };
    const items = context.pages.map((page) => `<li><a href="${page.slug}.html">${page.title}</a>${page.date ? ` <time>${page.date}</time>` : ''}${page.tags.length ? ` <span class="tags">${page.tags.join(', ')}</span>` : ''}</li>`).join('\n');
    const body = `<main>\n<h1>Pages</h1>\n<ul>\n${items}\n</ul>\n</main>`;
    const rendered = renderer.render('index', templateContext) ?? document('Index', body);
    fs.writeFileSync(path.join(context.options.outputDir, 'index.html'), this.withLayout(templateContext, context.options.templatesDir, rendered, renderer));
  }
}

export default TemplatePlugin;
