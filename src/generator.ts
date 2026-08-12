import { promises as fs } from 'node:fs';
import path from 'node:path';
import matter from 'gray-matter';
import { marked } from 'marked';

export interface SiteOptions {
  contentDir?: string;
  outputDir?: string;
  templatesDir?: string;
}

export interface Page {
  source: string;
  output: string;
  title: string;
  date?: string;
  tags: string[];
  html: string;
  template?: string;
  layout?: string;
}

type Frontmatter = {
  title?: unknown;
  date?: unknown;
  tags?: unknown;
  template?: unknown;
  layout?: unknown;
};

const layout = (title: string, body: string): string => `<!doctype html>
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

function escapeHtml(value: string): string {
  return value.replace(/[&<>'"]/g, (character) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;',
  }[character] ?? character));
}

function metadataValue(value: unknown): string | undefined {
  return value instanceof Date ? value.toISOString().slice(0, 10) :
    typeof value === 'string' || typeof value === 'number' ? String(value) : undefined;
}

function tagsValue(value: unknown): string[] {
  if (Array.isArray(value)) return value.map(String);
  if (typeof value === 'string') return value.split(',').map((tag) => tag.trim()).filter(Boolean);
  return [];
}

function templateValue(value: unknown): string | undefined {
  return typeof value === 'string' && value.trim() ? value.trim() : undefined;
}

async function existingFile(directory: string, name: string, extensions: string[]): Promise<string | undefined> {
  const candidates = path.extname(name) ? [name] : extensions.map((extension) => `${name}${extension}`);
  for (const candidate of candidates) {
    const file = path.join(directory, candidate);
    try {
      const stat = await fs.stat(file);
      if (stat.isFile()) return file;
    } catch {
      // A missing optional template is handled by the built-in renderer.
    }
  }
  return undefined;
}

function handlebarsValue(context: Record<string, unknown>, name: string): unknown {
  if (name === 'this' || name === '.') return context;
  if (name.startsWith('this.')) return handlebarsValue(context, name.slice(5));
  return name.split('.').reduce<unknown>((value, key) => {
    if (value && typeof value === 'object') return (value as Record<string, unknown>)[key];
    return undefined;
  }, context);
}

function renderTemplate(source: string, context: Record<string, unknown>, partials: Record<string, string>): string {
  const withBlocks = source.replace(/{{#each\s+([\w.$-]+)}}([\s\S]*?){{\/each}}/g,
    (_match, name: string, block: string) => {
      const values = handlebarsValue(context, name);
      return Array.isArray(values)
        ? values.map((value) => renderTemplate(block, (value && typeof value === 'object'
          ? value : { this: value }) as Record<string, unknown>, partials)).join('')
        : '';
    });
  const withPartials = withBlocks.replace(/{{>\s*([\w./-]+)(?:\s+[^}]*)?}}/g, (_match, name: string) => {
    const partial = partials[name] ?? partials[name.replace(/\.(?:hbs|handlebars|ejs)$/i, '')];
    return partial ? renderTemplate(partial, context, partials) : '';
  });
  return withPartials
    .replace(/{{{\s*([\w.$-]+)\s*}}}/g, (_match, name: string) => String(handlebarsValue(context, name) ?? ''))
    .replace(/{{\s*([\w.$-]+)\s*}}/g, (_match, name: string) => escapeHtml(String(handlebarsValue(context, name) ?? '')));
}

async function loadPartials(directory: string): Promise<Record<string, string>> {
  const result: Record<string, string> = {};
  let entries;
  try {
    entries = await fs.readdir(directory, { withFileTypes: true });
  } catch {
    return result;
  }
  for (const entry of entries) {
    if (!entry.isFile() || !/\.(hbs|handlebars|ejs)$/i.test(entry.name)) continue;
    const name = entry.name.replace(/\.(hbs|handlebars|ejs)$/i, '');
    result[name] = await fs.readFile(path.join(directory, entry.name), 'utf8');
  }
  return result;
}

async function markdownFiles(directory: string): Promise<string[]> {
  const entries = await fs.readdir(directory, { withFileTypes: true });
  const files: string[] = [];
  for (const entry of entries) {
    const file = path.join(directory, entry.name);
    if (entry.isDirectory()) files.push(...await markdownFiles(file));
    else if (entry.isFile() && /\.md$/i.test(entry.name)) files.push(file);
  }
  return files.sort((a, b) => a.localeCompare(b));
}

export async function buildSite(options: SiteOptions = {}): Promise<Page[]> {
  const contentDir = path.resolve(options.contentDir ?? './content');
  const outputDir = path.resolve(options.outputDir ?? './dist');
  const templatesDir = path.resolve(options.templatesDir ?? './templates');
  const partials = await loadPartials(path.join(templatesDir, 'partials'));
  const files = await markdownFiles(contentDir);
  const pages: Page[] = [];

  await fs.rm(outputDir, { recursive: true, force: true });
  await fs.mkdir(outputDir, { recursive: true });

  for (const file of files) {
    const parsed = matter(await fs.readFile(file, 'utf8'));
    const metadata = parsed.data as Frontmatter;
    const relative = path.relative(contentDir, file);
    const output = relative.replace(/\.md$/i, '.html');
    const title = metadataValue(metadata.title) ?? path.basename(relative, path.extname(relative));
    const date = metadataValue(metadata.date);
    const tags = tagsValue(metadata.tags);
    const template = templateValue(metadata.template);
    const layoutName = templateValue(metadata.layout);
    const content = await marked.parse(parsed.content);
    const details = [date ? `<time datetime="${escapeHtml(date)}">${escapeHtml(date)}</time>` : '',
      tags.length ? `<ul class="tags">${tags.map((tag) => `<li>${escapeHtml(tag)}</li>`).join('')}</ul>` : '']
      .filter(Boolean).join('\n');
    const body = `<main>\n  <article>\n    <h1>${escapeHtml(title)}</h1>\n    ${details}\n    ${content}  </article>\n</main>`;
    const context: Record<string, unknown> = {
      ...(parsed.data as Record<string, unknown>), title, date, tags, content, body,
    };
    const templateFile = await existingFile(templatesDir, template ?? 'default', ['.hbs', '.handlebars', '.ejs']);
    const pageBody = templateFile ? renderTemplate(await fs.readFile(templateFile, 'utf8'), context, partials) : body;
    const selectedLayout = layoutName ?? (templateFile ? 'default' : undefined);
    const layoutFile = selectedLayout
      ? await existingFile(path.join(templatesDir, 'layouts'), selectedLayout, ['.hbs', '.handlebars', '.ejs'])
      : undefined;
    const html = layoutFile
      ? renderTemplate(await fs.readFile(layoutFile, 'utf8'), { ...context, body: pageBody }, partials)
      : layout(title, pageBody);
    const page = { source: relative, output, title, date, tags, template, layout: selectedLayout, html };
    pages.push(page);
    const destination = path.join(outputDir, output);
    await fs.mkdir(path.dirname(destination), { recursive: true });
    await fs.writeFile(destination, page.html, 'utf8');
  }

  const links = pages.map((page) => `    <li><a href="${page.output.split(path.sep).join('/')}">${escapeHtml(page.title)}</a>${page.date ? ` <time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : ''}</li>`).join('\n');
  const indexBody = `<main>\n  <h1>Pages</h1>\n  <ul>\n${links}\n  </ul>\n</main>`;
  const indexTemplate = await existingFile(templatesDir, 'index', ['.hbs', '.handlebars', '.ejs']);
  const indexLayout = await existingFile(path.join(templatesDir, 'layouts'), 'default', ['.hbs', '.handlebars', '.ejs']);
  const indexContext = { title: 'Pages', pages, content: indexBody, body: indexBody } as Record<string, unknown>;
  const renderedIndex = indexTemplate
    ? renderTemplate(await fs.readFile(indexTemplate, 'utf8'), indexContext, partials)
    : indexBody;
  await fs.writeFile(path.join(outputDir, 'index.html'), indexLayout
    ? renderTemplate(await fs.readFile(indexLayout, 'utf8'), { ...indexContext, body: renderedIndex }, partials)
    : layout('Pages', renderedIndex), 'utf8');
  return pages;
}
