import { mkdir, readdir, readFile, writeFile } from 'node:fs/promises';
import { extname, relative, resolve, sep } from 'node:path';
import Handlebars from 'handlebars';
import type { Page, PageData } from '../generator';
import type { Plugin, PluginContext } from '../plugin';

function escapeHtml(value: string): string {
  return value.replace(/[&<>"']/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[character]!);
}

async function templateFiles(directory: string): Promise<string[]> {
  try {
    const entries = await readdir(directory, { withFileTypes: true });
    const paths = await Promise.all(entries.map(async (entry) => {
      const path = resolve(directory, entry.name);
      if (entry.isDirectory()) return templateFiles(path);
      return entry.isFile() && extname(entry.name) === '.hbs' ? [path] : [];
    }));
    return paths.flat();
  } catch (error: unknown) {
    if (error instanceof Error && 'code' in error && error.code === 'ENOENT') return [];
    throw error;
  }
}

function pageDocument(page: Page): string {
  const metadata = [page.date ? `<time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : '', page.tags.length ? `<p>Tags: ${page.tags.map(escapeHtml).join(', ')}</p>` : ''].filter(Boolean).join('\n');
  return `<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>${escapeHtml(page.title)}</title></head>
<body>
<main>
<article>
<h1>${escapeHtml(page.title)}</h1>
${metadata}
${page.html}
</article>
</main>
</body>
</html>
`;
}

function indexDocument(pages: Page[]): string {
  const items = pages.map((page) => {
    const details = [page.date, page.tags.length ? page.tags.join(', ') : ''].filter(Boolean).join(' | ');
    return `<li><a href="${encodeURI(page.outputPath.split(sep).join('/'))}">${escapeHtml(page.title)}</a>${details ? ` <small>${escapeHtml(details)}</small>` : ''}</li>`;
  }).join('\n');
  return `<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Pages</title></head>
<body><main><h1>Pages</h1><ul>${items}</ul></main></body>
</html>
`;
}

async function readTemplate(path: string): Promise<string | undefined> {
  try { return await readFile(path, 'utf8'); } catch (error: unknown) {
    if (error instanceof Error && 'code' in error && error.code === 'ENOENT') return undefined;
    throw error;
  }
}

export class TemplatePlugin implements Plugin {
  private data = new Map<Page, PageData>();

  beforeBuild(context: PluginContext): void {
    this.data = new Map(context.sourcePages.map(({ page, data }) => [page, data]));
  }

  async onFile(page: Page, context: PluginContext): Promise<void> {
    const data = this.data.get(page)!;
    const engine = Handlebars.create();
    const partialsDir = resolve(context.options.templatesDir, 'partials');
    await Promise.all((await templateFiles(partialsDir)).map(async (path) => engine.registerPartial(relative(partialsDir, path).replace(/\\/g, '/').replace(/\.hbs$/, ''), await readFile(path, 'utf8'))));
    const templateName = typeof data.template === 'string' && data.template.trim() ? data.template : 'default';
    const template = await readTemplate(resolve(context.options.templatesDir, templateName.endsWith('.hbs') ? templateName : `${templateName}.hbs`));
    let document: string;
    if (!template) {
      if (templateName !== 'default') throw new Error(`Template not found: ${templateName}`);
      document = pageDocument(page);
    } else {
      const pageContext = { ...data, ...page, content: page.html };
      document = engine.compile(template)(pageContext);
      const layoutName = typeof data.layout === 'string' && data.layout.trim() ? data.layout : 'default';
      const layout = await readTemplate(resolve(context.options.templatesDir, 'layouts', layoutName.endsWith('.hbs') ? layoutName : `${layoutName}.hbs`));
      if (layout) document = engine.compile(layout)({ ...pageContext, body: new Handlebars.SafeString(document) });
      else if (layoutName !== 'default') throw new Error(`Layout not found: ${layoutName}`);
    }
    const destination = resolve(context.options.outputDir, page.outputPath);
    await mkdir(resolve(destination, '..'), { recursive: true });
    await writeFile(destination, document);
  }

  async afterBuild(context: PluginContext): Promise<void> {
    await writeFile(resolve(context.options.outputDir, 'index.html'), indexDocument(context.pages));
  }
}
