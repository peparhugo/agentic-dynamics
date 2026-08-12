import { readdir, readFile, rm, mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import matter from 'gray-matter';
import { marked } from 'marked';
import Handlebars from 'handlebars';
import ejs from 'ejs';

export interface PageMetadata {
  title?: string;
  date?: string;
  tags: string[];
  [key: string]: unknown;
}

export interface Page {
  sourcePath: string;
  outputPath: string;
  url: string;
  metadata: PageMetadata;
  content: string;
}

export interface BuildOptions {
  contentDir?: string;
  outputDir?: string;
  templatesDir?: string;
  defaultTemplate?: string;
  defaultLayout?: string;
}

const escapeHtml = (value: string): string => value
  .replaceAll('&', '&amp;')
  .replaceAll('<', '&lt;')
  .replaceAll('>', '&gt;')
  .replaceAll('"', '&quot;')
  .replaceAll("'", '&#39;');

const displayTitle = (page: Page): string => page.metadata.title ||
  path.basename(page.sourcePath, path.extname(page.sourcePath));

async function markdownFiles(directory: string): Promise<string[]> {
  const entries = await readdir(directory, { withFileTypes: true });
  const files: string[] = [];
  for (const entry of entries) {
    const entryPath = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      files.push(...await markdownFiles(entryPath));
    } else if (entry.isFile() && path.extname(entry.name).toLowerCase() === '.md') {
      files.push(entryPath);
    }
  }
  return files.sort();
}

async function filesWithExtensions(directory: string, extensions: string[]): Promise<string[]> {
  const entries = await readdir(directory, { withFileTypes: true });
  const files: string[] = [];
  for (const entry of entries) {
    const entryPath = path.join(directory, entry.name);
    if (entry.isDirectory()) files.push(...await filesWithExtensions(entryPath, extensions));
    else if (entry.isFile() && extensions.includes(path.extname(entry.name).toLowerCase())) files.push(entryPath);
  }
  return files;
}

async function loadPage(sourcePath: string, contentDir: string, outputDir: string): Promise<Page> {
  const source = await readFile(sourcePath, 'utf8');
  const parsed = matter(source);
  const rawTags = parsed.data.tags;
  const tags = Array.isArray(rawTags)
    ? rawTags.map(String)
    : typeof rawTags === 'string' ? rawTags.split(',').map((tag) => tag.trim()).filter(Boolean) : [];
  const relativePath = path.relative(contentDir, sourcePath);
  const outputRelativePath = relativePath.replace(/\.md$/i, '.html');
  const outputPath = path.join(outputDir, outputRelativePath);
  const url = `/${outputRelativePath.split(path.sep).join('/')}`;
  return {
    sourcePath,
    outputPath,
    url,
    metadata: { ...parsed.data, tags },
    content: await marked.parse(parsed.content)
  };
}

type Template = { source: string; path: string; engine: 'hbs' | 'ejs' };

async function findTemplate(directory: string, name: string, subdirectory = ''): Promise<Template | undefined> {
  const requested = path.extname(name) ? [name] : [`${name}.hbs`, `${name}.ejs`];
  for (const filename of requested) {
    const templatePath = path.join(directory, subdirectory, filename);
    try {
      return {
        source: await readFile(templatePath, 'utf8'),
        path: templatePath,
        engine: path.extname(templatePath).toLowerCase() === '.ejs' ? 'ejs' : 'hbs'
      };
    } catch (error: unknown) {
      if ((error as NodeJS.ErrnoException).code !== 'ENOENT') throw error;
    }
  }
  return undefined;
}

async function registerPartials(templatesDir: string): Promise<void> {
  const partialDir = path.join(templatesDir, 'partials');
  const files = await filesWithExtensions(partialDir, ['.hbs', '.ejs']).catch(() => []);
  for (const file of files) {
    const name = path.relative(partialDir, file).replace(/\.(hbs|ejs)$/i, '').split(path.sep).join('/');
    if (path.extname(file).toLowerCase() === '.hbs') {
      const source = await readFile(file, 'utf8');
      Handlebars.registerPartial(name, source);
      Handlebars.registerPartial(`partials/${name}`, source);
    }
  }
}

async function renderTemplate(template: Template, data: Record<string, unknown>): Promise<string> {
  if (template.engine === 'hbs') return Handlebars.compile(template.source)(data);
  return ejs.render(template.source, data, { filename: template.path });
}

const renderPage = (page: Page): string => {
  const title = escapeHtml(displayTitle(page));
  const date = page.metadata.date ? `<time>${escapeHtml(String(page.metadata.date))}</time>` : '';
  const tags = page.metadata.tags.length > 0
    ? `<ul class="tags">${page.metadata.tags.map((tag) => `<li>${escapeHtml(tag)}</li>`).join('')}</ul>`
    : '';
  return `<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>${title}</title></head>
<body><main><h1>${title}</h1>${date}${tags}<article>${page.content}</article></main></body>
</html>
`;
};

async function renderWithTemplates(
  page: Page,
  templatesDir: string,
  defaultTemplate: string,
  defaultLayout?: string
): Promise<string> {
  const requestedTemplate = typeof page.metadata.template === 'string' ? page.metadata.template : defaultTemplate;
  const template = await findTemplate(templatesDir, requestedTemplate);
  if (!template) {
    if (typeof page.metadata.template === 'string') throw new Error(`Template not found: ${requestedTemplate}`);
    return renderPage(page);
  }

  const data = { ...page.metadata, title: displayTitle(page), content: page.content, page };
  let rendered = await renderTemplate(template, data);
  const layoutName = typeof page.metadata.layout === 'string' ? page.metadata.layout : defaultLayout;
  if (layoutName) {
    const layout = await findTemplate(templatesDir, layoutName, 'layouts');
    if (!layout) throw new Error(`Layout not found: ${layoutName}`);
    rendered = await renderTemplate(layout, { ...data, body: rendered });
  }
  return rendered;
}

const renderIndex = (pages: Page[]): string => `<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Index</title></head>
<body><main><h1>Pages</h1><ul>${pages.map((page) =>
  `<li><a href="${escapeHtml(page.url)}">${escapeHtml(displayTitle(page))}</a></li>`).join('')}
</ul></main></body>
</html>
`;

export async function buildSite(options: BuildOptions = {}): Promise<Page[]> {
  const contentDir = path.resolve(options.contentDir || './content');
  const outputDir = path.resolve(options.outputDir || './dist');
  const templatesDir = path.resolve(options.templatesDir || './templates');
  await registerPartials(templatesDir);
  const sources = await markdownFiles(contentDir);
  const pages = await Promise.all(sources.map((source) => loadPage(source, contentDir, outputDir)));
  pages.sort((a, b) => displayTitle(a).localeCompare(displayTitle(b)));

  await rm(outputDir, { recursive: true, force: true });
  await mkdir(outputDir, { recursive: true });
  await Promise.all(pages.map(async (page) => {
    await mkdir(path.dirname(page.outputPath), { recursive: true });
    await writeFile(page.outputPath, await renderWithTemplates(page, templatesDir, options.defaultTemplate || 'default', options.defaultLayout), 'utf8');
  }));
  await writeFile(path.join(outputDir, 'index.html'), renderIndex(pages), 'utf8');
  return pages;
}
