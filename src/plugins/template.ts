import { promises as fs } from 'node:fs';
import path from 'node:path';
import Handlebars from 'handlebars';
import { BuildContext, Page, Plugin } from '../types';

interface TemplateEngine {
  renderPage(page: Page): string;
  renderIndex(pages: Page[]): string;
}

const escapeHtml = (value: string): string => value
  .replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
  .replaceAll('"', '&quot;').replaceAll("'", '&#39;');

function document(title: string, body: string): string {
  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>${escapeHtml(title)}</title>
</head>
<body>
${body}
</body>
</html>
`;
}

function renderPageBody(page: Page): string {
  const metadata = [
    page.date ? `<time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : '',
    page.tags.length ? `<ul class="tags">${page.tags.map(tag => `<li>${escapeHtml(tag)}</li>`).join('')}</ul>` : ''
  ].filter(Boolean).join('\n');
  return `<main>
  <article>
    <header>
      <h1>${escapeHtml(page.title)}</h1>
      ${metadata}
    </header>
    ${page.html}
  </article>
</main>`;
}

function renderIndexBody(pages: Page[]): string {
  const items = pages.map(page => {
    const date = page.date ? ` <time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : '';
    return `    <li><a href="${escapeHtml(page.url)}">${escapeHtml(page.title)}</a>${date}</li>`;
  }).join('\n');
  return `<main>
  <h1>Pages</h1>
  <ul>
${items}
  </ul>
</main>`;
}

async function hbsFiles(directory: string): Promise<string[]> {
  let entries;
  try {
    entries = await fs.readdir(directory, { withFileTypes: true });
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return [];
    throw error;
  }
  const files = await Promise.all(entries.map(async entry => {
    const entryPath = path.join(directory, entry.name);
    if (entry.isDirectory()) return hbsFiles(entryPath);
    return /\.hbs$/i.test(entry.name) ? [entryPath] : [];
  }));
  return files.flat().sort((left, right) => left.localeCompare(right));
}

function templateName(value: unknown, fallback: string): string {
  if (typeof value !== 'string' || !value.trim()) return fallback;
  const name = value.trim().replace(/\.hbs$/i, '');
  if (path.isAbsolute(name) || name.split(/[\\/]/).includes('..')) {
    throw new Error(`Invalid template name: ${value}`);
  }
  return name;
}

async function loadTemplateEngine(templatesDir: string): Promise<TemplateEngine> {
  const handlebars = Handlebars.create();
  const partialsDir = path.join(templatesDir, 'partials');
  await Promise.all((await hbsFiles(partialsDir)).map(async filename => {
    const relative = path.relative(partialsDir, filename).replace(/\.hbs$/i, '').split(path.sep).join('/');
    handlebars.registerPartial(relative, await fs.readFile(filename, 'utf8'));
  }));

  const templateFiles = (await hbsFiles(templatesDir)).filter(filename => {
    const relative = path.relative(templatesDir, filename);
    return !relative.startsWith(`layouts${path.sep}`) && !relative.startsWith(`partials${path.sep}`);
  });
  const layoutDir = path.join(templatesDir, 'layouts');
  const templates = new Map<string, Handlebars.TemplateDelegate>();
  const layouts = new Map<string, Handlebars.TemplateDelegate>();
  await Promise.all(templateFiles.map(async filename => {
    const name = path.relative(templatesDir, filename).replace(/\.hbs$/i, '').split(path.sep).join('/');
    templates.set(name, handlebars.compile(await fs.readFile(filename, 'utf8')));
  }));
  await Promise.all((await hbsFiles(layoutDir)).map(async filename => {
    const name = path.relative(layoutDir, filename).replace(/\.hbs$/i, '').split(path.sep).join('/');
    layouts.set(name, handlebars.compile(await fs.readFile(filename, 'utf8')));
  }));

  const applyLayout = (body: string, context: Record<string, unknown>, requested: unknown): string => {
    const name = templateName(requested, 'default');
    const layout = layouts.get(name);
    if (!layout) {
      if (requested !== undefined && requested !== null && requested !== '') throw new Error(`Layout not found: ${name}.hbs`);
      return body;
    }
    return layout({ ...context, body });
  };

  return {
    renderPage(page): string {
      const name = templateName(page.data.template, 'default');
      const template = templates.get(name);
      const context = { ...page.data, ...page, content: page.html };
      if (!template) {
        if (page.data.template !== undefined) throw new Error(`Template not found: ${name}.hbs`);
        if (page.data.layout !== undefined || layouts.has('default')) {
          return applyLayout(renderPageBody(page), context, page.data.layout);
        }
        return document(page.title, renderPageBody(page));
      }
      return applyLayout(template(context), context, page.data.layout);
    },
    renderIndex(pages): string {
      const template = templates.get('index');
      const context = { title: 'Pages', pages };
      if (template) return applyLayout(template(context), context, undefined);
      return layouts.has('default')
        ? applyLayout(renderIndexBody(pages), context, undefined)
        : document('Pages', renderIndexBody(pages));
    }
  };
}

export class TemplatePlugin implements Plugin {
  readonly name = 'templates';
  private templates?: TemplateEngine;

  async beforeBuild(context: BuildContext): Promise<void> {
    this.templates = await loadTemplateEngine(context.templatesDir);
    await fs.mkdir(context.outputDir, { recursive: true });
  }

  async afterBuild(context: BuildContext): Promise<void> {
    if (!this.templates) throw new Error('TemplatePlugin has not been initialized');
    const templates = this.templates;
    await Promise.all(context.pages.map(async page => {
      await fs.mkdir(path.dirname(page.outputPath), { recursive: true });
      await fs.writeFile(page.outputPath, templates.renderPage(page), 'utf8');
    }));
    await fs.writeFile(path.join(context.outputDir, 'index.html'), templates.renderIndex(context.pages), 'utf8');
  }
}
