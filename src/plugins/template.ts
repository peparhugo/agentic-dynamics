import { promises as fs } from 'node:fs';
import path from 'node:path';
import Handlebars from 'handlebars';
import { BuildContext, GeneratedPage, Page, PageMetadata, Plugin } from '../plugin';

function escapeHtml(value: string): string {
  return value.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;').replaceAll("'", '&#39;');
}

async function fileExists(filePath: string): Promise<boolean> {
  try {
    return (await fs.stat(filePath)).isFile();
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return false;
    throw error;
  }
}

async function loadPartials(directory: string): Promise<Record<string, string>> {
  const partials: Record<string, string> = {};
  let entries;
  try {
    entries = await fs.readdir(directory, { withFileTypes: true });
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return partials;
    throw error;
  }
  await Promise.all(entries.map(async (entry) => {
    const filePath = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      const nested = await loadPartials(filePath);
      for (const [name, contents] of Object.entries(nested)) partials[`${entry.name}/${name}`] = contents;
    } else if (entry.isFile() && entry.name.endsWith('.hbs')) {
      const contents = await fs.readFile(filePath, 'utf8');
      partials[entry.name] = contents;
      partials[entry.name.replace(/\.hbs$/i, '')] = contents;
    }
  }));
  return partials;
}

function resolveTemplate(directory: string, name: unknown, kind: 'template' | 'layout'): string | undefined {
  if (typeof name !== 'string' || !name.trim()) return undefined;
  const base = kind === 'layout' ? path.join(directory, 'layouts') : directory;
  const relative = name.trim().endsWith('.hbs') ? name.trim() : `${name.trim()}.hbs`;
  const resolved = path.resolve(base, relative);
  if (resolved !== base && !resolved.startsWith(`${base}${path.sep}`)) throw new Error(`Invalid ${kind} path: ${name}`);
  return resolved;
}

function defaultPage(metadata: PageMetadata, body: string): string {
  const title = escapeHtml(metadata.title);
  const date = metadata.date ? `<time datetime="${escapeHtml(metadata.date)}">${escapeHtml(metadata.date)}</time>` : '';
  const tags = metadata.tags.length ? `<ul class="tags">${metadata.tags.map((tag) => `<li>${escapeHtml(tag)}</li>`).join('')}</ul>` : '';
  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>${title}</title>
</head>
<body>
  <nav><a href="/index.html">Home</a></nav>
  <main>
    <article>
      <header><h1>${title}</h1>${date}${tags}</header>
      ${body}
    </article>
  </main>
</body>
</html>
`;
}

function defaultIndex(pages: GeneratedPage[]): string {
  const items = pages.map((page) => {
    const date = page.date ? ` <time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : '';
    return `<li><a href="${escapeHtml(page.url)}">${escapeHtml(page.title)}</a>${date}</li>`;
  }).join('\n      ');
  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Pages</title>
</head>
<body>
  <main>
    <h1>Pages</h1>
    <ul>
      ${items}
    </ul>
  </main>
</body>
</html>
`;
}

export class TemplatePlugin implements Plugin {
  readonly name = 'templates';
  private handlebars = Handlebars.create();

  async onStart(context: BuildContext): Promise<void> {
    this.handlebars = Handlebars.create();
    this.handlebars.registerPartial(await loadPartials(path.join(context.options.templatesDir, 'partials')));
  }

  async onFile(page: Page, context: BuildContext): Promise<void> {
    const templatesDir = context.options.templatesDir;
    const selected = resolveTemplate(templatesDir, page.data.template, 'template');
    const fallback = path.join(templatesDir, 'default.hbs');
    const template = selected ?? (await fileExists(fallback) ? fallback : undefined);
    const templateContext = { ...page.data, title: page.title, date: page.date, tags: page.tags, body: page.body };
    if (selected && !await fileExists(selected)) throw new Error(`Template does not exist: ${selected}`);
    page.html = template
      ? this.handlebars.compile(await fs.readFile(template, 'utf8'))(templateContext)
      : defaultPage(page, page.body);

    const layout = resolveTemplate(templatesDir, page.data.layout, 'layout');
    if (layout) {
      if (!await fileExists(layout)) throw new Error(`Layout does not exist: ${layout}`);
      page.html = this.handlebars.compile(await fs.readFile(layout, 'utf8'))({ ...templateContext, body: page.html });
    }
  }

  async afterBuild(context: BuildContext): Promise<void> {
    await fs.writeFile(path.join(context.options.outputDir, 'index.html'), defaultIndex(context.pages), 'utf8');
  }
}
