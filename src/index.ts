import { promises as fs } from 'node:fs';
import path from 'node:path';
import matter from 'gray-matter';
import Handlebars from 'handlebars';
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
  sourcePath: string;
  outputPath: string;
  url: string;
}

interface RenderedPage extends Page {
  html: string;
  data: Record<string, unknown>;
  template?: string;
  layout?: string | false;
}

function escapeHtml(value: string): string {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function templateName(value: unknown): string | undefined {
  return typeof value === 'string' && value.trim() ? value.trim() : undefined;
}

async function isFile(filePath: string): Promise<boolean> {
  try {
    return (await fs.stat(filePath)).isFile();
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') {
      return false;
    }
    throw error;
  }
}

function templatePath(directory: string, name: string): string {
  const withExtension = path.extname(name) ? name : `${name}.hbs`;
  const resolved = path.resolve(directory, withExtension);
  const relative = path.relative(directory, resolved);
  if (relative === '..' || relative.startsWith(`..${path.sep}`) || path.isAbsolute(relative)) {
    throw new Error(`Template must be inside ${directory}: ${name}`);
  }
  return resolved;
}

async function templateFiles(directory: string, base = directory): Promise<string[]> {
  let entries;
  try {
    entries = await fs.readdir(directory, { withFileTypes: true });
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') {
      return [];
    }
    throw error;
  }
  const nested = await Promise.all(entries.map(async (entry) => {
    const absolutePath = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      return templateFiles(absolutePath, base);
    }
    return entry.isFile() && /\.hbs$/i.test(entry.name)
      ? [path.relative(base, absolutePath)]
      : [];
  }));
  return nested.flat();
}

async function loadPartials(templatesDir: string): Promise<Record<string, string>> {
  const directory = path.join(templatesDir, 'partials');
  const files = await templateFiles(directory);
  const partials: Record<string, string> = {};
  await Promise.all(files.map(async (file) => {
    const name = file.slice(0, -path.extname(file).length).split(path.sep).join('/');
    partials[name] = await fs.readFile(path.join(directory, file), 'utf8');
  }));
  return partials;
}

function asDate(value: unknown): string | undefined {
  if (value instanceof Date) {
    return Number.isNaN(value.getTime()) ? undefined : value.toISOString().slice(0, 10);
  }
  if (typeof value === 'string' || typeof value === 'number') {
    return String(value);
  }
  return undefined;
}

function asTags(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value.map(String);
  }
  if (typeof value === 'string') {
    return value.split(',').map((tag) => tag.trim()).filter(Boolean);
  }
  return [];
}

function outputPathFor(relativePath: string): string {
  const parsed = path.parse(relativePath);
  return path.join(parsed.dir, `${parsed.name}.html`);
}

function urlFor(outputPath: string): string {
  const normalized = outputPath.split(path.sep).join('/');
  return `/${normalized}`;
}

async function markdownFiles(directory: string, base = directory): Promise<string[]> {
  const entries = await fs.readdir(directory, { withFileTypes: true });
  const nested = await Promise.all(entries.map(async (entry) => {
    const absolutePath = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      return markdownFiles(absolutePath, base);
    }
    return entry.isFile() && /\.md$/i.test(entry.name)
      ? [path.relative(base, absolutePath)]
      : [];
  }));
  return nested.flat().sort((left, right) => left.localeCompare(right));
}

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

function pageDocument(page: RenderedPage): string {
  const date = page.date ? `\n  <time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : '';
  const tags = page.tags.length > 0
    ? `\n  <ul class="tags">${page.tags.map((tag) => `<li>${escapeHtml(tag)}</li>`).join('')}</ul>`
    : '';
  return document(page.title, `  <main>
  <article>
  <header>
  <h1>${escapeHtml(page.title)}</h1>${date}${tags}
  </header>
  ${page.html}
  </article>
  </main>`);
}

function indexDocument(pages: Page[]): string {
  const items = pages.map((page) => {
    const date = page.date ? ` <time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : '';
    return `  <li><a href="${escapeHtml(page.url)}">${escapeHtml(page.title)}</a>${date}</li>`;
  }).join('\n');
  return document('Pages', `  <main>\n  <h1>Pages</h1>\n  <ul>\n${items}\n  </ul>\n  </main>`);
}

export async function buildSite(options: BuildOptions = {}): Promise<Page[]> {
  const contentDir = path.resolve(options.contentDir ?? 'content');
  const outputDir = path.resolve(options.outputDir ?? 'dist');
  const templatesDir = path.resolve(options.templatesDir ?? 'templates');
  const defaultTemplatePath = templatePath(templatesDir, 'default');
  const defaultLayoutPath = templatePath(path.join(templatesDir, 'layouts'), 'default');
  const [hasDefaultTemplate, hasDefaultLayout, partials] = await Promise.all([
    isFile(defaultTemplatePath),
    isFile(defaultLayoutPath),
    loadPartials(templatesDir)
  ]);
  const handlebars = Handlebars.create();
  handlebars.registerPartial(partials);
  const files = await markdownFiles(contentDir);
  const pages = await Promise.all(files.map(async (sourcePath): Promise<RenderedPage> => {
    const source = await fs.readFile(path.join(contentDir, sourcePath), 'utf8');
    const parsed = matter(source);
    const title = typeof parsed.data.title === 'string' && parsed.data.title.trim()
      ? parsed.data.title.trim()
      : path.parse(sourcePath).name;
    const outputPath = outputPathFor(sourcePath);
    return {
      title,
      date: asDate(parsed.data.date),
      tags: asTags(parsed.data.tags),
      sourcePath,
      outputPath,
      url: urlFor(outputPath),
      html: await marked.parse(parsed.content),
      data: parsed.data,
      template: templateName(parsed.data.template),
      layout: parsed.data.layout === false ? false : templateName(parsed.data.layout)
    };
  }));

  const destinations = new Set<string>();
  for (const page of pages) {
    if (page.outputPath === 'index.html' || destinations.has(page.outputPath)) {
      throw new Error(`Output path collision: ${page.outputPath}`);
    }
    destinations.add(page.outputPath);
  }

  await fs.rm(outputDir, { recursive: true, force: true });
  await fs.mkdir(outputDir, { recursive: true });
  await Promise.all(pages.map(async (page) => {
    const destination = path.join(outputDir, page.outputPath);
    const context: Record<string, unknown> = {
      ...page.data,
      title: page.title,
      date: page.date,
      tags: page.tags,
      sourcePath: page.sourcePath,
      outputPath: page.outputPath,
      url: page.url,
      content: page.html,
      body: page.html
    };
    const selectedTemplate = page.template
      ? templatePath(templatesDir, page.template)
      : hasDefaultTemplate ? defaultTemplatePath : undefined;
    let rendered = selectedTemplate
      ? handlebars.compile(await fs.readFile(selectedTemplate, 'utf8'))(context)
      : pageDocument(page);
    const selectedLayout = page.layout === false
      ? undefined
      : page.layout
        ? templatePath(path.join(templatesDir, 'layouts'), page.layout)
        : hasDefaultLayout ? defaultLayoutPath : undefined;
    if (selectedLayout) {
      rendered = handlebars.compile(await fs.readFile(selectedLayout, 'utf8'))({ ...context, body: rendered });
    }
    await fs.mkdir(path.dirname(destination), { recursive: true });
    await fs.writeFile(destination, rendered, 'utf8');
  }));
  await fs.writeFile(path.join(outputDir, 'index.html'), indexDocument(pages), 'utf8');

  return pages.map(({ html: _html, data: _data, template: _template, layout: _layout, ...page }) => page);
}
