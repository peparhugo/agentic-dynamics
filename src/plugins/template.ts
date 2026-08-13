import { promises as fs } from 'node:fs';
import path from 'node:path';
import Handlebars from 'handlebars';
import { Plugin, PluginContext, PluginPage } from '../plugin';

const styles = `body{max-width:48rem;margin:3rem auto;padding:0 1.25rem;font:18px/1.6 system-ui,sans-serif;color:#202124}a{color:#075985}header{border-bottom:1px solid #ddd;margin-bottom:2rem}h1{line-height:1.2}.meta{color:#666;font-size:.9rem}.pages{padding:0;list-style:none}.pages li{margin:1rem 0}`;

function escapeHtml(value: string): string {
  return value.replace(/[&<>'"]/g, (character) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
  })[character] ?? character);
}

function layout(title: string, body: string, metadata = ''): string {
  const safeTitle = escapeHtml(title);
  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>${safeTitle}</title>
  <style>${styles}</style>
</head>
<body>
  <header><a href="/index.html">Home</a></header>
  <main>
    <h1>${safeTitle}</h1>${metadata}
    ${body}
  </main>
</body>
</html>
`;
}

async function fileExists(file: string): Promise<boolean> {
  try {
    return (await fs.stat(file)).isFile();
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return false;
    throw error;
  }
}

async function templateFiles(directory: string): Promise<string[]> {
  let entries;
  try {
    entries = await fs.readdir(directory, { withFileTypes: true });
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return [];
    throw error;
  }
  const files = await Promise.all(entries.map(async (entry) => {
    const location = path.join(directory, entry.name);
    if (entry.isDirectory()) return templateFiles(location);
    return /\.hbs$/i.test(entry.name) ? [location] : [];
  }));
  return files.flat().sort();
}

function templatePath(directory: string, name: string): string {
  const relative = path.normalize(name.endsWith('.hbs') ? name : `${name}.hbs`);
  const resolved = path.resolve(directory, relative);
  if (resolved !== path.resolve(directory) && !resolved.startsWith(`${path.resolve(directory)}${path.sep}`)) {
    throw new Error(`Template must be inside ${directory}: ${name}`);
  }
  return resolved;
}

async function requestedTemplate(directory: string, value: unknown, fallback: string): Promise<string | undefined> {
  if (value === false || value === null) return undefined;
  const explicit = typeof value === 'string' && value.trim() ? value.trim() : undefined;
  const file = templatePath(directory, explicit ?? fallback);
  if (await fileExists(file)) return file;
  if (explicit) throw new Error(`Template not found: ${file}`);
  return undefined;
}

export class TemplatePlugin implements Plugin {
  readonly name = 'templates';
  private engine = Handlebars.create();
  private templatesDir = '';
  private partialSignature = '';
  private compiled = new Map<string, { source: string; template: Handlebars.TemplateDelegate }>();

  async beforeBuild(context: PluginContext): Promise<void> {
    this.templatesDir = context.options.templatesDir;
    const partialsDir = path.join(this.templatesDir, 'partials');
    const partials = await Promise.all((await templateFiles(partialsDir)).map(async (file) => ({
      file,
      source: await fs.readFile(file, 'utf8')
    })));
    const signature = partials.map(({ file, source }) => `${file}\0${source}`).join('\0');
    if (signature === this.partialSignature) return;
    this.partialSignature = signature;
    this.engine = Handlebars.create();
    this.compiled.clear();
    for (const { file, source } of partials) {
      const name = path.relative(partialsDir, file).replace(/\.hbs$/i, '').split(path.sep).join('/');
      this.engine.registerPartial(name, source);
    }
  }

  private async render(file: string, context: Record<string, unknown>): Promise<string> {
    const source = await fs.readFile(file, 'utf8');
    let cached = this.compiled.get(file);
    if (!cached || cached.source !== source) {
      cached = { source, template: this.engine.compile(source) };
      this.compiled.set(file, cached);
    }
    return cached.template(context);
  }

  async onFile(page: PluginPage): Promise<void> {
    const metadataParts = [page.date, page.tags.length > 0 ? page.tags.join(', ') : undefined].filter(Boolean);
    const metadata = metadataParts.length > 0
      ? `\n    <p class="meta">${metadataParts.map((part) => escapeHtml(String(part))).join(' &middot; ')}</p>`
      : '';
    const context = { ...page.data, title: page.title, date: page.date, tags: page.tags, content: page.content, body: page.content };
    const pageTemplate = await requestedTemplate(this.templatesDir, page.data.template, 'default');
    const renderedPage = pageTemplate
      ? await this.render(pageTemplate, context)
      : undefined;
    const layoutTemplate = await requestedTemplate(path.join(this.templatesDir, 'layouts'), page.data.layout, 'default');
    page.output = layoutTemplate
      ? await this.render(layoutTemplate, { ...context, body: renderedPage ?? page.content })
      : renderedPage ?? layout(page.title, page.content, metadata);
  }

  async afterBuild(context: PluginContext): Promise<void> {
    const links = context.pages.length === 0
      ? '<p>No pages found.</p>'
      : `<ul class="pages">${context.pages.map((page) => {
        const date = page.date ? ` <span class="meta">${escapeHtml(page.date)}</span>` : '';
        return `<li><a href="${page.url}">${escapeHtml(page.title)}</a>${date}</li>`;
      }).join('')}</ul>`;
    await fs.writeFile(path.join(context.options.outputDir, 'index.html'), layout('Pages', links));
  }
}
