import { promises as fs } from 'node:fs';
import path from 'node:path';
import matter from 'gray-matter';
import Handlebars from 'handlebars';
import { marked } from 'marked';

export interface PageMetadata {
  title: string;
  date?: string;
  tags: string[];
}

export interface GeneratedPage extends PageMetadata {
  sourcePath: string;
  outputPath: string;
  url: string;
}

export interface BuildOptions {
  contentDir?: string;
  outputDir?: string;
  templatesDir?: string;
}

function escapeHtml(value: string): string {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
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
    return value.map(String).map((tag) => tag.trim()).filter(Boolean);
  }
  if (typeof value === 'string') {
    return value.split(',').map((tag) => tag.trim()).filter(Boolean);
  }
  return [];
}

async function markdownFiles(directory: string): Promise<string[]> {
  let entries;
  try {
    entries = await fs.readdir(directory, { withFileTypes: true });
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') {
      throw new Error(`Content directory does not exist: ${directory}`);
    }
    throw error;
  }

  const files = await Promise.all(entries.map(async (entry) => {
    const entryPath = path.join(directory, entry.name);
    if (entry.isDirectory()) return markdownFiles(entryPath);
    return entry.isFile() && /\.md$/i.test(entry.name) ? [entryPath] : [];
  }));
  return files.flat().sort();
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

function templatePath(directory: string, name: unknown, kind: 'template' | 'layout'): string | undefined {
  if (typeof name !== 'string' || !name.trim()) return undefined;
  const baseDirectory = kind === 'layout' ? path.join(directory, 'layouts') : directory;
  const relativeName = name.trim().endsWith('.hbs') ? name.trim() : `${name.trim()}.hbs`;
  const resolved = path.resolve(baseDirectory, relativeName);
  if (resolved !== baseDirectory && !resolved.startsWith(`${baseDirectory}${path.sep}`)) {
    throw new Error(`Invalid ${kind} path: ${name}`);
  }
  return resolved;
}

function pageTemplate(metadata: PageMetadata, body: string): string {
  const title = escapeHtml(metadata.title);
  const date = metadata.date
    ? `<time datetime="${escapeHtml(metadata.date)}">${escapeHtml(metadata.date)}</time>`
    : '';
  const tags = metadata.tags.length
    ? `<ul class="tags">${metadata.tags.map((tag) => `<li>${escapeHtml(tag)}</li>`).join('')}</ul>`
    : '';

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

function indexTemplate(pages: GeneratedPage[]): string {
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

export async function buildSite(options: BuildOptions = {}): Promise<GeneratedPage[]> {
  const contentDir = path.resolve(options.contentDir ?? './content');
  const outputDir = path.resolve(options.outputDir ?? './dist');
  const templatesDir = path.resolve(options.templatesDir ?? './templates');
  const files = await markdownFiles(contentDir);
  const partials = await loadPartials(path.join(templatesDir, 'partials'));
  const handlebars = Handlebars.create();
  handlebars.registerPartial(partials);
  const defaultTemplatePath = path.join(templatesDir, 'default.hbs');

  await fs.rm(outputDir, { recursive: true, force: true });
  await fs.mkdir(outputDir, { recursive: true });

  const pages: GeneratedPage[] = [];
  for (const sourcePath of files) {
    const source = await fs.readFile(sourcePath, 'utf8');
    const parsed = matter(source);
    const relativePath = path.relative(contentDir, sourcePath);
    const outputRelativePath = relativePath.replace(/\.md$/i, '.html');
    const outputPath = path.join(outputDir, outputRelativePath);
    const title = typeof parsed.data.title === 'string' && parsed.data.title.trim()
      ? parsed.data.title.trim()
      : path.basename(sourcePath, path.extname(sourcePath));
    const metadata: PageMetadata = {
      title,
      date: normalizeDate(parsed.data.date),
      tags: normalizeTags(parsed.data.tags),
    };
    const body = marked.parse(parsed.content, { async: false }) as string;
    const context = { ...parsed.data, ...metadata, body };
    const selectedTemplatePath = templatePath(templatesDir, parsed.data.template, 'template');
    let html: string;

    if (selectedTemplatePath) {
      if (!await fileExists(selectedTemplatePath)) {
        throw new Error(`Template does not exist: ${selectedTemplatePath}`);
      }
      html = handlebars.compile(await fs.readFile(selectedTemplatePath, 'utf8'))(context);
    } else if (await fileExists(defaultTemplatePath)) {
      html = handlebars.compile(await fs.readFile(defaultTemplatePath, 'utf8'))(context);
    } else {
      html = pageTemplate(metadata, body);
    }

    const selectedLayoutPath = templatePath(templatesDir, parsed.data.layout, 'layout');
    if (selectedLayoutPath) {
      if (!await fileExists(selectedLayoutPath)) {
        throw new Error(`Layout does not exist: ${selectedLayoutPath}`);
      }
      html = handlebars.compile(await fs.readFile(selectedLayoutPath, 'utf8'))({ ...context, body: html });
    }

    await fs.mkdir(path.dirname(outputPath), { recursive: true });
    await fs.writeFile(outputPath, html, 'utf8');
    pages.push({
      ...metadata,
      sourcePath,
      outputPath,
      url: outputRelativePath.split(path.sep).join('/'),
    });
  }

  pages.sort((left, right) => left.title.localeCompare(right.title));
  await fs.writeFile(path.join(outputDir, 'index.html'), indexTemplate(pages), 'utf8');
  return pages;
}
