import { promises as fs } from 'node:fs';
import path from 'node:path';
import matter from 'gray-matter';
import { marked } from 'marked';

export interface BuildOptions {
  contentDir?: string;
  outputDir?: string;
  templatesDir?: string;
}

export interface Page {
  title: string;
  date?: string;
  tags: string[];
  html: string;
  sourcePath: string;
  outputPath: string;
}

interface Frontmatter {
  title?: unknown;
  date?: unknown;
  tags?: unknown;
  template?: unknown;
  layout?: unknown;
}

const escapeHtml = (value: string): string => value
  .replaceAll('&', '&amp;')
  .replaceAll('<', '&lt;')
  .replaceAll('>', '&gt;')
  .replaceAll('"', '&quot;')
  .replaceAll("'", '&#39;');

const normalizeTags = (value: unknown): string[] => {
  if (Array.isArray(value)) return value.map(String).filter(Boolean);
  if (typeof value === 'string') return value.split(',').map((tag) => tag.trim()).filter(Boolean);
  return [];
};

const normalizeDate = (value: unknown): string | undefined => {
  if (value instanceof Date) return value.toISOString().slice(0, 10);
  if (typeof value === 'string' || typeof value === 'number') return String(value);
  return undefined;
};

async function markdownFiles(directory: string): Promise<string[]> {
  const entries = await fs.readdir(directory, { withFileTypes: true });
  const files: string[] = [];
  for (const entry of entries) {
    const entryPath = path.join(directory, entry.name);
    if (entry.isDirectory()) files.push(...await markdownFiles(entryPath));
    else if (entry.isFile() && /\.(md|markdown)$/i.test(entry.name)) files.push(entryPath);
  }
  return files.sort();
}

const outputName = (relativePath: string): string =>
  relativePath.replace(/\.(md|markdown)$/i, '.html');

const pageDocument = (page: Page): string => {
  const date = page.date ? `<time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : '';
  const tags = page.tags.length > 0
    ? `<ul class="tags">${page.tags.map((tag) => `<li>${escapeHtml(tag)}</li>`).join('')}</ul>`
    : '';
  return `<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>${escapeHtml(page.title)}</title></head>
<body><main><h1>${escapeHtml(page.title)}</h1>${date}${tags}<article>${page.html}</article></main></body>
</html>
`;
};

const indexDocument = (pages: Page[]): string => `<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Index</title></head>
<body><main><h1>Pages</h1><ul>${pages.map((page) => `<li><a href="${encodeURI(page.outputPath)}">${escapeHtml(page.title)}</a>${page.date ? ` <time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : ''}</li>`).join('')}</ul></main></body>
</html>
`;

type TemplateContext = Record<string, unknown>;

const valueAt = (context: TemplateContext, expression: string): unknown => {
  const name = expression.trim();
  if (name === 'this' || name === '.') return context.this ?? context;
  return name.split('.').reduce<unknown>((value, part) => {
    if (value && typeof value === 'object') return (value as Record<string, unknown>)[part];
    return undefined;
  }, context);
};

const stringValue = (value: unknown): string => value == null ? '' : String(value);

const templateFile = async (directory: string, name: string, subdirectory = ''): Promise<string | undefined> => {
  const requested = name.trim();
  const candidates = path.extname(requested) ? [requested] : [`${requested}.hbs`, `${requested}.ejs`];
  for (const candidate of candidates) {
    const file = path.join(directory, subdirectory, candidate);
    try {
      if ((await fs.stat(file)).isFile()) return file;
    } catch {
      // Try the next supported extension.
    }
  }
  return undefined;
};

const renderTemplate = (source: string, context: TemplateContext, partials: Record<string, string>): string => {
  const render = (input: string, values: TemplateContext): string => {
    let output = input;
    output = output.replace(/{{#each\s+([^}]+)}}([\s\S]*?){{\/each}}/g, (_match, expression: string, body: string) => {
      const items = valueAt(values, expression);
      if (!Array.isArray(items)) return '';
      return items.map((item, index) => render(body, { ...values, this: item, '@index': index })).join('');
    });
    output = output.replace(/{{#if\s+([^}]+)}}([\s\S]*?){{\/if}}/g, (_match, expression: string, body: string) => {
      return valueAt(values, expression) ? render(body, values) : '';
    });
    output = output.replace(/{{>\s*([\w./-]+)\s*}}/g, (_match, name: string) => {
      const partial = partials[name] ?? partials[path.basename(name)];
      return partial ? render(partial, values) : '';
    });
    output = output.replace(/<%-\s*include\(['"]([^'"]+)['"]\)\s*%>/g, (_match, name: string) => {
      const partial = partials[name] ?? partials[path.basename(name)];
      return partial ? render(partial, values) : '';
    });
    output = output.replace(/{{{\s*([^}]+)\s*}}}/g, (_match, expression: string) => stringValue(valueAt(values, expression)));
    output = output.replace(/{{\s*([^{}#/>][^{}]*)\s*}}/g, (_match, expression: string) => escapeHtml(stringValue(valueAt(values, expression))));
    output = output.replace(/<%=\s*([^%]+)\s*%>/g, (_match, expression: string) => escapeHtml(stringValue(valueAt(values, expression))));
    output = output.replace(/<%-\s*([^%]+)\s*%>/g, (_match, expression: string) => stringValue(valueAt(values, expression)));
    return output;
  };
  return render(source, context);
};

async function loadPartials(directory: string): Promise<Record<string, string>> {
  const result: Record<string, string> = {};
  let entries: import('node:fs').Dirent[] = [];
  try { entries = await fs.readdir(path.join(directory, 'partials'), { withFileTypes: true }); } catch { return result; }
  for (const entry of entries) {
    if (entry.isFile() && /\.(hbs|ejs)$/i.test(entry.name)) {
      result[entry.name.replace(/\.(hbs|ejs)$/i, '')] = await fs.readFile(path.join(directory, 'partials', entry.name), 'utf8');
    }
  }
  return result;
}

const frontmatterName = (value: unknown): string | undefined => typeof value === 'string' && value.trim() ? value.trim() : undefined;

async function renderPage(page: Page, metadata: Frontmatter, templatesDir: string): Promise<string> {
  const templateName = frontmatterName(metadata.template);
  const templatePath = templateName
    ? await templateFile(templatesDir, templateName)
    : await templateFile(templatesDir, 'default');
  if (templateName && !templatePath) throw new Error(`Template not found: ${templateName}`);
  const context: TemplateContext = {
    ...metadata,
    title: page.title,
    date: page.date,
    tags: page.tags,
    content: page.html,
    body: page.html,
    html: page.html,
    page,
  };
  const partials = await loadPartials(templatesDir);
  let document = templatePath
    ? renderTemplate(await fs.readFile(templatePath, 'utf8'), context, partials)
    : pageDocument(page);
  const layoutName = frontmatterName(metadata.layout);
  if (layoutName && layoutName !== 'none') {
    const layoutPath = await templateFile(templatesDir, layoutName, 'layouts');
    if (!layoutPath) throw new Error(`Layout template not found: ${layoutName}`);
    document = renderTemplate(await fs.readFile(layoutPath, 'utf8'), { ...context, body: document, content: document }, partials);
  }
  return document;
}

export async function buildSite(options: BuildOptions = {}): Promise<Page[]> {
  const contentDir = path.resolve(options.contentDir ?? './content');
  const outputDir = path.resolve(options.outputDir ?? './dist');
  const templatesDir = path.resolve(options.templatesDir ?? './templates');
  const files = await markdownFiles(contentDir);
  const pages: Page[] = [];
  const pageMetadata = new Map<Page, Frontmatter>();

  for (const sourcePath of files) {
    const parsed = matter(await fs.readFile(sourcePath, 'utf8'));
    const metadata = parsed.data as Frontmatter;
    const relativePath = path.relative(contentDir, sourcePath).split(path.sep).join('/');
    const outputPath = outputName(relativePath);
    const page: Page = {
      title: typeof metadata.title === 'string' && metadata.title.trim() ? metadata.title : path.basename(relativePath, path.extname(relativePath)),
      date: normalizeDate(metadata.date),
      tags: normalizeTags(metadata.tags),
      html: marked.parse(parsed.content),
      sourcePath,
      outputPath,
    };
    pages.push(page);
    pageMetadata.set(page, metadata);
  }

  pages.sort((a, b) => (b.date ?? '').localeCompare(a.date ?? '') || a.outputPath.localeCompare(b.outputPath));
  await fs.rm(outputDir, { recursive: true, force: true });
  await fs.mkdir(outputDir, { recursive: true });
  await fs.writeFile(path.join(outputDir, 'index.html'), indexDocument(pages));
  for (const page of pages) {
    const destination = path.join(outputDir, page.outputPath);
    await fs.mkdir(path.dirname(destination), { recursive: true });
    await fs.writeFile(destination, await renderPage(page, pageMetadata.get(page) ?? {}, templatesDir));
  }
  return pages;
}
