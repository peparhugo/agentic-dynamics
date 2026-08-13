import { mkdir, readdir, readFile, writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { extname, join, relative, resolve } from 'node:path';
import Handlebars from 'handlebars';
import { BuildContext, BuildPage, document, escapeHtml, Plugin } from '../plugin';

interface RenderContext {
  title: string;
  date?: string;
  tags: string[];
  content: string;
  body?: string;
  [key: string]: unknown;
}

async function templateFiles(directory: string): Promise<string[]> {
  try {
    const entries = await readdir(directory, { withFileTypes: true });
    const paths = await Promise.all(entries.map(async (entry) => {
      const path = join(directory, entry.name);
      if (entry.isDirectory()) return templateFiles(path);
      return entry.isFile() && extname(entry.name).toLowerCase() === '.hbs' ? [path] : [];
    }));
    return paths.flat();
  } catch (error: unknown) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return [];
    throw error;
  }
}

export class TemplatePlugin implements Plugin {
  private templates = new Map<string, Handlebars.TemplateDelegate>();

  async onStart(context: BuildContext): Promise<void> {
    this.templates.clear();
    const files = await templateFiles(context.templatesDir);
    const sources = await Promise.all(files.map(async (file) => ({ file, source: await readFile(file, 'utf8') })));
    context.templateHash = createHash('sha256').update(sources
      .sort((a, b) => a.file.localeCompare(b.file))
      .map(({ file, source }) => `${relative(context.templatesDir, file)}\0${source}`)
      .join('\0')).digest('hex');
    await Promise.all(sources.map(async ({ file, source }) => {
      const name = relative(context.templatesDir, file).replace(/\\/g, '/').replace(/\.hbs$/i, '');
      this.templates.set(name, Handlebars.compile(source));
    }));
    for (const [name, template] of this.templates) {
      if (name.startsWith('partials/')) Handlebars.registerPartial(name.slice('partials/'.length), template);
    }
  }

  async onFile(page: BuildPage, context: BuildContext): Promise<void> {
    const metadata = [page.date, page.tags.length ? `Tags: ${page.tags.map(escapeHtml).join(', ')}` : ''].filter(Boolean).join(' | ');
    const renderContext: RenderContext = { ...page.data, title: page.title, date: page.date, tags: page.tags, content: page.html.trim() };
    const templateName = page.template ?? 'default';
    const pageBody = this.templates.get(templateName)?.(renderContext)
      ?? `    <article>\n      <h1>${escapeHtml(page.title)}</h1>${metadata ? `\n      <p>${metadata}</p>` : ''}\n      ${renderContext.content}\n    </article>`;
    const layoutName = page.layout ?? (this.templates.has('layouts/default') ? 'default' : undefined);
    const html = layoutName
      ? this.templates.get(`layouts/${layoutName}`)?.({ ...renderContext, body: pageBody }) ?? pageBody
      : this.templates.has(templateName) ? pageBody : document(page.title, pageBody);
    const destination = join(context.outputDir, page.outputPath);
    await mkdir(resolve(destination, '..'), { recursive: true });
    await writeFile(destination, html);
  }
}
