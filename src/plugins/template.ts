import { promises as fs } from 'node:fs';
import path from 'node:path';
import Handlebars from 'handlebars';
import type { Plugin, PluginContext, PluginPage } from '../types';

function escapeHtml(value: string): string {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function pageTemplate(page: PluginPage): string {
  const title = escapeHtml(page.title);
  const depth = page.url.split('/').length - 1;
  const homeUrl = `${'../'.repeat(depth)}index.html`;
  const metadata = [
    page.date ? `<time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : '',
    page.tags.length > 0
      ? `<ul class="tags">${page.tags.map((tag) => `<li>${escapeHtml(tag)}</li>`).join('')}</ul>`
      : '',
  ].filter(Boolean).join('\n');

  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>${title}</title>
</head>
<body>
  <nav><a href="${homeUrl}">Home</a></nav>
  <main>
    <article>
      <header><h1>${title}</h1>${metadata ? `\n${metadata}` : ''}</header>
      ${page.html}
    </article>
  </main>
</body>
</html>
`;
}

async function isDirectory(directory: string): Promise<boolean> {
  return fs.stat(directory).then((stat) => stat.isDirectory()).catch(() => false);
}

async function findFiles(directory: string): Promise<string[]> {
  const entries = await fs.readdir(directory, { withFileTypes: true });
  const files = await Promise.all(entries.map(async (entry) => {
    const entryPath = path.join(directory, entry.name);
    if (entry.isDirectory()) return findFiles(entryPath);
    return /\.hbs$/i.test(entry.name) ? [entryPath] : [];
  }));
  return files.flat().sort();
}

async function findTemplateFile(directory: string, name: string): Promise<string> {
  const requested = path.resolve(directory, name.endsWith('.hbs') ? name : `${name}.hbs`);
  const relative = path.relative(directory, requested);
  if (relative.startsWith('..') || path.isAbsolute(relative)) {
    throw new Error(`Template must be inside ${directory}: ${name}`);
  }
  if (await fs.stat(requested).then((stat) => stat.isFile()).catch(() => false)) return requested;
  throw new Error(`Template not found: ${name}`);
}

export class TemplatePlugin implements Plugin {
  private handlebars = Handlebars.create();

  async beforeBuild(context: PluginContext): Promise<void> {
    this.handlebars = Handlebars.create();
    const partialsDir = path.join(context.templatesDir, 'partials');
    if (!await isDirectory(partialsDir)) return;
    await Promise.all((await findFiles(partialsDir)).map(async (file) => {
      const name = path.relative(partialsDir, file).replace(/\.hbs$/i, '').split(path.sep).join('/');
      this.handlebars.registerPartial(name, await fs.readFile(file, 'utf8'));
    }));
  }

  async onFile(page: PluginPage, context: PluginContext): Promise<void> {
    const defaultTemplate = path.join(context.templatesDir, 'default.hbs');
    const hasDefault = await fs.stat(defaultTemplate).then((stat) => stat.isFile()).catch(() => false);
    if (!page.template && !hasDefault && !page.layout) {
      page.output = pageTemplate(page);
      return;
    }

    const templateContext = {
      ...page.frontmatter,
      title: page.title,
      date: page.date,
      tags: page.tags,
      url: page.url,
      content: new this.handlebars.SafeString(page.html),
    };
    let rendered = page.template || hasDefault
      ? this.handlebars.compile(await fs.readFile(
        page.template ? await findTemplateFile(context.templatesDir, page.template) : defaultTemplate,
        'utf8',
      ))(templateContext)
      : page.html;

    if (page.layout) {
      const layout = await findTemplateFile(path.join(context.templatesDir, 'layouts'), page.layout);
      rendered = this.handlebars.compile(await fs.readFile(layout, 'utf8'))({
        ...templateContext,
        body: new this.handlebars.SafeString(rendered),
      });
    }
    page.output = rendered;
  }
}
