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
  outputPath: string;
  url: string;
}

const styles = `body{max-width:48rem;margin:3rem auto;padding:0 1.25rem;font:18px/1.6 system-ui,sans-serif;color:#202124}a{color:#075985}header{border-bottom:1px solid #ddd;margin-bottom:2rem}h1{line-height:1.2}.meta{color:#666;font-size:.9rem}.pages{padding:0;list-style:none}.pages li{margin:1rem 0}`;

function escapeHtml(value: string): string {
  return value.replace(/[&<>'"]/g, (character) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    "'": '&#39;',
    '"': '&quot;'
  })[character] ?? character);
}

function normalizeDate(value: unknown): string | undefined {
  if (value instanceof Date && !Number.isNaN(value.valueOf())) {
    return value.toISOString().slice(0, 10);
  }
  if (typeof value === 'string' || typeof value === 'number') {
    return String(value);
  }
  return undefined;
}

function normalizeTags(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value.map(String);
  }
  if (typeof value === 'string') {
    return value.split(',').map((tag) => tag.trim()).filter(Boolean);
  }
  return [];
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

async function createTemplateEngine(templatesDir: string): Promise<typeof Handlebars> {
  const engine = Handlebars.create();
  const partialsDir = path.join(templatesDir, 'partials');
  for (const file of await templateFiles(partialsDir)) {
    const name = path.relative(partialsDir, file).replace(/\.hbs$/i, '').split(path.sep).join('/');
    engine.registerPartial(name, await fs.readFile(file, 'utf8'));
  }
  return engine;
}

async function markdownFiles(directory: string): Promise<string[]> {
  const entries = await fs.readdir(directory, { withFileTypes: true });
  const files = await Promise.all(entries.map(async (entry) => {
    const location = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      return markdownFiles(location);
    }
    return /\.md$/i.test(entry.name) ? [location] : [];
  }));
  return files.flat().sort();
}

function outputDetails(file: string, contentDir: string, outputDir: string): Pick<Page, 'outputPath' | 'url'> {
  const relative = path.relative(contentDir, file).replace(/\.md$/i, '.html');
  return {
    outputPath: path.join(outputDir, relative),
    url: relative.split(path.sep).map(encodeURIComponent).join('/')
  };
}

export async function buildSite(options: BuildOptions = {}): Promise<Page[]> {
  const contentDir = path.resolve(options.contentDir ?? './content');
  const outputDir = path.resolve(options.outputDir ?? './dist');
  const templatesDir = path.resolve(options.templatesDir ?? './templates');
  const files = await markdownFiles(contentDir);
  const templates = await createTemplateEngine(templatesDir);

  await fs.rm(outputDir, { recursive: true, force: true });
  await fs.mkdir(outputDir, { recursive: true });

  const pages = await Promise.all(files.map(async (file) => {
    const source = await fs.readFile(file, 'utf8');
    const parsed = matter(source);
    const details = outputDetails(file, contentDir, outputDir);
    const fallbackTitle = path.basename(file, path.extname(file));
    const title = typeof parsed.data.title === 'string' ? parsed.data.title : fallbackTitle;
    const date = normalizeDate(parsed.data.date);
    const tags = normalizeTags(parsed.data.tags);
    const metadataParts = [date, tags.length > 0 ? tags.join(', ') : undefined].filter(Boolean);
    const metadata = metadataParts.length > 0
      ? `\n    <p class="meta">${metadataParts.map((part) => escapeHtml(String(part))).join(' &middot; ')}</p>`
      : '';
    const content = await marked.parse(parsed.content);
    const context = { ...parsed.data, title, date, tags, content, body: content };
    const pageTemplate = await requestedTemplate(templatesDir, parsed.data.template, 'default');
    const renderedPage = pageTemplate
      ? templates.compile(await fs.readFile(pageTemplate, 'utf8'))(context)
      : undefined;
    const layoutTemplate = await requestedTemplate(path.join(templatesDir, 'layouts'), parsed.data.layout, 'default');
    const output = layoutTemplate
      ? templates.compile(await fs.readFile(layoutTemplate, 'utf8'))({ ...context, body: renderedPage ?? content })
      : renderedPage ?? layout(title, content, metadata);

    await fs.mkdir(path.dirname(details.outputPath), { recursive: true });
    await fs.writeFile(details.outputPath, output);
    return { title, date, tags, ...details };
  }));

  pages.sort((left, right) => {
    if (left.date && right.date && left.date !== right.date) {
      return right.date.localeCompare(left.date);
    }
    return left.title.localeCompare(right.title);
  });

  const links = pages.length === 0
    ? '<p>No pages found.</p>'
    : `<ul class="pages">${pages.map((page) => {
      const date = page.date ? ` <span class="meta">${escapeHtml(page.date)}</span>` : '';
      return `<li><a href="${page.url}">${escapeHtml(page.title)}</a>${date}</li>`;
    }).join('')}</ul>`;
  await fs.writeFile(path.join(outputDir, 'index.html'), layout('Pages', links));

  return pages;
}
