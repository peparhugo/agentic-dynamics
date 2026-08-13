import { promises as fs } from 'node:fs';
import path from 'node:path';
import matter from 'gray-matter';
import Handlebars from 'handlebars';
import { marked } from 'marked';

export interface Frontmatter {
  title?: string;
  date?: string | Date;
  tags?: string[] | string;
  template?: string;
  layout?: string;
  [key: string]: unknown;
}

export interface Page {
  title: string;
  date?: string;
  tags: string[];
  html: string;
  outputPath: string;
  url: string;
  template?: string;
  layout?: string;
  data?: Frontmatter;
}

export interface BuildOptions {
  contentDir?: string;
  outputDir?: string;
  templateDir?: string;
}

const escapeHtml = (value: string): string =>
  value.replace(/[&<>'"]/g, (character) => {
    const entities: Record<string, string> = {
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      "'": '&#39;',
      '"': '&quot;',
    };
    return entities[character];
  });

const normalizeDate = (value: unknown): string | undefined => {
  if (value instanceof Date && !Number.isNaN(value.valueOf())) {
    return value.toISOString().slice(0, 10);
  }
  if (typeof value === 'string' && value.trim()) {
    return value.trim();
  }
  return undefined;
};

const normalizeTags = (value: unknown): string[] => {
  if (Array.isArray(value)) {
    return value.filter((tag): tag is string => typeof tag === 'string').map((tag) => tag.trim()).filter(Boolean);
  }
  if (typeof value === 'string') {
    return value.split(',').map((tag) => tag.trim()).filter(Boolean);
  }
  return [];
};

const titleFromFilename = (filename: string): string => {
  const name = path.basename(filename, path.extname(filename));
  return name
    .split(/[-_]+/)
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
};

export function parseMarkdown(source: string, relativePath: string): Page {
  const parsed = matter(source);
  const data = parsed.data as Frontmatter;
  const title = typeof data.title === 'string' && data.title.trim()
    ? data.title.trim()
    : titleFromFilename(relativePath);
  const htmlPath = relativePath.replace(/\.md$/i, '.html');
  const outputPath = htmlPath === 'index.html' ? 'index-page.html' : htmlPath;

  return {
    title,
    date: normalizeDate(data.date),
    tags: normalizeTags(data.tags),
    html: marked.parse(parsed.content, { async: false }) as string,
    outputPath,
    url: outputPath.split(path.sep).join('/'),
    template: typeof data.template === 'string' && data.template.trim() ? data.template.trim() : undefined,
    layout: typeof data.layout === 'string' && data.layout.trim() ? data.layout.trim() : undefined,
    data,
  };
}

const renderLayout = (title: string, content: string): string => `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>${escapeHtml(title)}</title>
</head>
<body>
${content}
</body>
</html>
`;

export function renderPage(page: Page): string {
  const date = page.date ? `\n  <time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : '';
  const tags = page.tags.length
    ? `\n  <ul class="tags">${page.tags.map((tag) => `<li>${escapeHtml(tag)}</li>`).join('')}</ul>`
    : '';
  return renderLayout(page.title, `  <main>\n  <article>\n  <header>\n  <h1>${escapeHtml(page.title)}</h1>${date}${tags}\n  </header>\n${page.html}  </article>\n  </main>`);
}

export function renderIndex(pages: Page[]): string {
  const items = pages.map((page) => {
    const date = page.date ? ` <time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : '';
    return `    <li><a href="${escapeHtml(page.url)}">${escapeHtml(page.title)}</a>${date}</li>`;
  }).join('\n');
  const list = items ? `\n  <ul>\n${items}\n  </ul>` : '\n  <p>No pages found.</p>';
  return renderLayout('Pages', `  <main>\n  <h1>Pages</h1>${list}\n  </main>`);
}

const templateName = (name: string): string => name.toLowerCase().endsWith('.hbs') ? name : `${name}.hbs`;

const safeTemplatePath = (directory: string, name: string): string => {
  const resolvedDirectory = path.resolve(directory);
  const resolved = path.resolve(directory, templateName(name));
  const relative = path.relative(resolvedDirectory, resolved);
  if (relative.startsWith('..') || path.isAbsolute(relative)) {
    throw new Error(`Template path must stay within ${resolvedDirectory}: ${name}`);
  }
  return resolved;
};

const readNamedTemplate = async (directory: string, name: string, kind: string): Promise<string> => {
  const filename = safeTemplatePath(directory, name);
  return fs.readFile(filename, 'utf8').catch((error: unknown) => {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') throw new Error(`${kind} not found: ${name}`);
    throw error;
  });
};

const loadPartials = async (handlebars: typeof Handlebars, partialsDir: string): Promise<void> => {
  const entries = await fs.readdir(partialsDir, { withFileTypes: true }).catch((error: unknown) => {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return [];
    throw error;
  });
  await Promise.all(entries.map(async (entry) => {
    if (!entry.isFile() || !entry.name.toLowerCase().endsWith('.hbs')) return;
    const source = await fs.readFile(path.join(partialsDir, entry.name), 'utf8');
    handlebars.registerPartial(path.basename(entry.name, path.extname(entry.name)), source);
  }));
};

const renderTemplatedPage = async (page: Page, templatesDir: string, handlebars: typeof Handlebars): Promise<string> => {
  const template = await readNamedTemplate(templatesDir, page.template ?? 'default', 'Template');
  const context = { ...page.data, ...page, content: page.html };
  const content = handlebars.compile(template)(context);
  const layoutName = page.layout ?? 'default';
  const layout = await readNamedTemplate(path.join(templatesDir, 'layouts'), layoutName, 'Layout');
  return handlebars.compile(layout)({ ...context, body: content });
};

async function markdownFiles(directory: string, base = directory): Promise<string[]> {
  const entries = await fs.readdir(directory, { withFileTypes: true });
  const files = await Promise.all(entries.map(async (entry): Promise<string[]> => {
    const fullPath = path.join(directory, entry.name);
    if (entry.isDirectory()) return markdownFiles(fullPath, base);
    return entry.isFile() && /\.md$/i.test(entry.name) ? [path.relative(base, fullPath)] : [];
  }));
  return files.flat().sort((left, right) => left.localeCompare(right));
}

export async function buildSite(options: BuildOptions = {}): Promise<Page[]> {
  const contentDir = path.resolve(options.contentDir ?? './content');
  const outputDir = path.resolve(options.outputDir ?? './dist');
  const templatesDir = path.resolve(options.templateDir ?? './templates');
  const outputRelativeToContent = path.relative(contentDir, outputDir);
  const contentRelativeToOutput = path.relative(outputDir, contentDir);
  const isWithin = (relativePath: string): boolean =>
    relativePath === '' || (!relativePath.startsWith('..') && !path.isAbsolute(relativePath));
  if (isWithin(outputRelativeToContent) || isWithin(contentRelativeToOutput)) {
    throw new Error('Content and output directories must not overlap');
  }

  const stats = await fs.stat(contentDir).catch(() => undefined);
  if (!stats?.isDirectory()) {
    throw new Error(`Content directory does not exist: ${contentDir}`);
  }

  const files = await markdownFiles(contentDir);
  const pages = await Promise.all(files.map(async (relativePath) => {
    const source = await fs.readFile(path.join(contentDir, relativePath), 'utf8');
    return parseMarkdown(source, relativePath);
  }));

  pages.sort((left, right) => {
    if (left.date && right.date && left.date !== right.date) return right.date.localeCompare(left.date);
    if (left.date !== right.date) return left.date ? -1 : 1;
    return left.title.localeCompare(right.title);
  });

  const templatesStats = await fs.stat(templatesDir).catch(() => undefined);
  const useTemplates = templatesStats?.isDirectory() ?? false;
  const handlebars = Handlebars.create();
  if (useTemplates) await loadPartials(handlebars, path.join(templatesDir, 'partials'));

  await fs.rm(outputDir, { recursive: true, force: true });
  await fs.mkdir(outputDir, { recursive: true });
  await Promise.all(pages.map(async (page) => {
    const destination = path.join(outputDir, page.outputPath);
    await fs.mkdir(path.dirname(destination), { recursive: true });
    await fs.writeFile(destination, useTemplates ? await renderTemplatedPage(page, templatesDir, handlebars) : renderPage(page), 'utf8');
  }));
  await fs.writeFile(path.join(outputDir, 'index.html'), renderIndex(pages), 'utf8');
  return pages;
}

export { startDevServer, type DevServer, type ServeOptions } from './server';
