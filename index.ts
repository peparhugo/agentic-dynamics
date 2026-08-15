import { promises as fs } from 'node:fs';
import path from 'node:path';
import { createServer, type IncomingMessage, type ServerResponse } from 'node:http';
import matter from 'gray-matter';
import { marked } from 'marked';
import chokidar, { type FSWatcher } from 'chokidar';
import { WebSocketServer, type WebSocket } from 'ws';

export interface Frontmatter {
  title?: string;
  date?: string;
  tags?: string[];
  template?: string;
  layout?: string;
  [key: string]: unknown;
}

export interface Page {
  sourcePath: string;
  outputPath: string;
  title: string;
  date?: string;
  tags: string[];
  html: string;
  frontmatter?: Frontmatter;
}

export interface BuildOptions {
  contentDir?: string;
  outputDir?: string;
  templatesDir?: string;
}

export interface ServeOptions extends BuildOptions {
  port?: number;
}

export interface DevServer {
  server: ReturnType<typeof createServer>;
  watcher: FSWatcher;
  close: () => Promise<void>;
}

export interface ParsedMarkdown {
  data: Frontmatter;
  content: string;
}

const markdownExtensions = new Set(['.md', '.markdown']);

function parseSimpleYaml(input: string): Frontmatter {
  const data: Frontmatter = {};
  for (const line of input.split(/\r?\n/)) {
    const separator = line.indexOf(':');
    if (separator < 0) continue;
    const key = line.slice(0, separator).trim();
    if (!key) continue;
    let value = line.slice(separator + 1).trim();
    if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) {
      value = value.slice(1, -1);
    }
    if (value.startsWith('[') && value.endsWith(']')) {
      data[key] = value.slice(1, -1).split(',').map((tag) => tag.trim().replace(/^['"]|['"]$/g, '')).filter(Boolean);
    } else {
      data[key] = value;
    }
  }
  return data;
}

export function parseMarkdown(source: string): ParsedMarkdown {
  let yaml: Frontmatter = {};
  let markdown = source;
  const match = source.match(/^---\s*\r?\n([\s\S]*?)\r?\n---\s*(?:\r?\n|$)/);
  if (match) {
    yaml = parseSimpleYaml(match[1]);
    markdown = source.slice(match[0].length);
  }

  // gray-matter still owns the document representation; custom YAML is merged
  // afterward because this project intentionally does not depend on a YAML engine.
  const parsed = matter(markdown);
  return { data: { ...parsed.data, ...yaml } as Frontmatter, content: parsed.content };
}

function escapeHtml(value: string): string {
  return value.replace(/[&<>"']/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[character] as string);
}

function titleFor(filePath: string, data: Frontmatter): string {
  if (typeof data.title === 'string' && data.title.trim()) return data.title.trim();
  return path.basename(filePath, path.extname(filePath)).replace(/[-_]+/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function tagsFor(data: Frontmatter): string[] {
  if (Array.isArray(data.tags)) return data.tags.map(String);
  if (typeof data.tags === 'string') return data.tags.split(',').map((tag) => tag.trim()).filter(Boolean);
  return [];
}

async function markdownFiles(directory: string, relative = ''): Promise<string[]> {
  const entries = await fs.readdir(path.join(directory, relative), { withFileTypes: true });
  const files: string[] = [];
  for (const entry of entries) {
    const child = path.join(relative, entry.name);
    if (entry.isDirectory()) files.push(...await markdownFiles(directory, child));
    else if (markdownExtensions.has(path.extname(entry.name).toLowerCase())) files.push(child);
  }
  return files.sort();
}

function pageTemplate(page: Page): string {
  return `<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n<title>${escapeHtml(page.title)}</title>\n</head>\n<body>\n<main>\n<h1>${escapeHtml(page.title)}</h1>\n${page.date ? `<time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>\n` : ''}${page.tags.length ? `<p class="tags">${page.tags.map((tag) => `<span>${escapeHtml(tag)}</span>`).join(' ')}</p>\n` : ''}${page.html}\n</main>\n</body>\n</html>\n`;
}

function indexTemplate(pages: Page[]): string {
  const items = pages.map((page) => `<li><a href="${escapeHtml(page.outputPath)}">${escapeHtml(page.title)}</a>${page.date ? ` <time datetime="${escapeHtml(page.date)}">${escapeHtml(page.date)}</time>` : ''}</li>`).join('\n');
  return `<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n<title>Index</title>\n</head>\n<body>\n<main>\n<h1>Index</h1>\n<ul>\n${items}\n</ul>\n</main>\n</body>\n</html>\n`;
}

type TemplateContext = Record<string, unknown>;

function valueFor(context: TemplateContext, name: string): unknown {
  return name.split('.').reduce<unknown>((value, key) => {
    if (value && typeof value === 'object') return (value as Record<string, unknown>)[key];
    return undefined;
  }, context);
}

function renderTemplate(source: string, context: TemplateContext, partials: Map<string, string>): string {
  let rendered = source;
  rendered = rendered.replace(/{{#each\s+([\w.]+)}}([\s\S]*?){{\/each}}/g, (_match, name: string, body: string) => {
    const values = valueFor(context, name);
    if (!Array.isArray(values)) return '';
    return values.map((item) => renderTemplate(body, {
      ...context,
      ...(item && typeof item === 'object' ? item as Record<string, unknown> : {}),
      this: item,
      '.': item,
    }, partials)).join('');
  });
  rendered = rendered.replace(/{{#if\s+([\w.]+)}}([\s\S]*?){{\/if}}/g, (_match, name: string, body: string) => {
    return valueFor(context, name) ? renderTemplate(body, context, partials) : '';
  });
  rendered = rendered.replace(/{{>\s*([\w./-]+)\s*}}/g, (_match, name: string) => {
    const partial = partials.get(name) ?? partials.get(name.replace(/\.hbs$|\.ejs$/i, ''));
    return partial ? renderTemplate(partial, context, partials) : '';
  });
  rendered = rendered.replace(/{{{\s*([\w.$]+)\s*}}}/g, (_match, name: string) => String(valueFor(context, name) ?? ''));
  rendered = rendered.replace(/{{\s*([\w.$]+)\s*}}/g, (_match, name: string) => escapeHtml(String(valueFor(context, name) ?? '')));
  return rendered;
}

async function loadTemplates(directory: string): Promise<{ templates: Map<string, string>; partials: Map<string, string>; layouts: Map<string, string> }> {
  const templates = new Map<string, string>();
  const partials = new Map<string, string>();
  const layouts = new Map<string, string>();
  async function readDirectory(current: string, target: Map<string, string>, prefix = ''): Promise<void> {
    let entries;
    try {
      entries = await fs.readdir(current, { withFileTypes: true });
    } catch (error: unknown) {
      if ((error as NodeJS.ErrnoException).code === 'ENOENT') return;
      throw error;
    }
    for (const entry of entries) {
      const fullPath = path.join(current, entry.name);
      if (entry.isDirectory()) await readDirectory(fullPath, target, prefix ? `${prefix}/${entry.name}` : entry.name);
      else if (/\.(hbs|ejs)$/i.test(entry.name)) {
        const name = `${prefix ? `${prefix}/` : ''}${entry.name}`;
        const content = await fs.readFile(fullPath, 'utf8');
        target.set(name, content);
        target.set(name.replace(/\.(hbs|ejs)$/i, ''), content);
      }
    }
  }
  await readDirectory(directory, templates);
  await readDirectory(path.join(directory, 'partials'), partials);
  await readDirectory(path.join(directory, 'layouts'), layouts);
  return { templates, partials, layouts };
}

function templateName(value: unknown, fallback: string): string {
  if (typeof value !== 'string' || !value.trim()) return fallback;
  return value.trim();
}

function templateContext(page: Page, data: Frontmatter, body: string): TemplateContext {
  return { ...data, ...page, content: body, body, page };
}

function renderWithLayout(content: string, context: TemplateContext, layout: string | undefined, partials: Map<string, string>): string {
  return layout ? renderTemplate(layout, { ...context, body: content }, partials) : content;
}

export async function buildSite(options: BuildOptions = {}): Promise<Page[]> {
  const contentDir = path.resolve(options.contentDir ?? './content');
  const outputDir = path.resolve(options.outputDir ?? './dist');
  const templatesDir = path.resolve(options.templatesDir ?? './templates');
  const loaded = await loadTemplates(templatesDir);
  const files = await markdownFiles(contentDir);
  const pages: Page[] = [];
  for (const relativeSource of files) {
    const source = await fs.readFile(path.join(contentDir, relativeSource), 'utf8');
    const parsed = parseMarkdown(source);
    const outputPath = relativeSource.replace(/\.(md|markdown)$/i, '.html').split(path.sep).join('/');
    const page: Page = {
      sourcePath: relativeSource.split(path.sep).join('/'),
      outputPath,
      title: titleFor(relativeSource, parsed.data),
      date: typeof parsed.data.date === 'string' ? parsed.data.date : undefined,
      tags: tagsFor(parsed.data),
      html: await marked.parse(parsed.content),
    };
    page.frontmatter = parsed.data;
    pages.push(page);
  }
  pages.sort((a, b) => (b.date ?? '').localeCompare(a.date ?? '') || a.outputPath.localeCompare(b.outputPath));
  await fs.rm(outputDir, { recursive: true, force: true });
  await fs.mkdir(outputDir, { recursive: true });
  for (const page of pages) {
    const destination = path.join(outputDir, page.outputPath);
    await fs.mkdir(path.dirname(destination), { recursive: true });
    const data = page.frontmatter ?? {};
    const selected = templateName(data.template, 'default');
    const template = loaded.templates.get(selected) ?? loaded.templates.get(`${selected}.hbs`) ?? loaded.templates.get(`${selected}.ejs`);
    const context = templateContext(page, data, page.html);
    const rendered = template ? renderTemplate(template, context, loaded.partials) : pageTemplate(page);
    const layoutName = template ? templateName(data.layout, 'default') : '';
    const layout = layoutName ? loaded.layouts.get(layoutName) ?? loaded.layouts.get(`${layoutName}.hbs`) ?? loaded.layouts.get(`${layoutName}.ejs`) : undefined;
    await fs.writeFile(destination, renderWithLayout(rendered, context, layout, loaded.partials), 'utf8');
  }
  const indexSource = loaded.templates.get('index') ?? loaded.templates.get('index.hbs') ?? loaded.templates.get('index.ejs');
  const index = indexSource ? renderTemplate(indexSource, { pages, title: 'Index' }, loaded.partials) : indexTemplate(pages);
  await fs.writeFile(path.join(outputDir, 'index.html'), index, 'utf8');
  return pages;
}

export function parseArgs(args: string[]): ServeOptions {
  const options: ServeOptions = {};
  for (let index = 0; index < args.length; index += 1) {
    if (args[index] === '--content' || args[index] === '--output' || args[index] === '--templates') {
      const value = args[++index];
      if (!value) throw new Error(`${args[index - 1]} requires a directory`);
      if (args[index - 1] === '--content') options.contentDir = value;
      else if (args[index - 1] === '--output') options.outputDir = value;
      else options.templatesDir = value;
    } else if (args[index] === '--port') {
      const value = args[++index];
      if (!value) throw new Error('--port requires a number');
      const port = Number(value);
      if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error('--port requires a valid port');
      options.port = port;
    }
  }
  return options;
}

const liveReloadScript = `<script>(function(){var socket=new WebSocket('ws://'+location.host+'/_ssg_live_reload');socket.onmessage=function(event){if(event.data==='reload')location.reload()};socket.onclose=function(){setTimeout(function(){location.reload()},1000)}})();</script>`;

export function injectLiveReload(html: string): string {
  if (html.includes("new WebSocket('ws://' + location.host)")) return html;
  const closingBody = html.search(/<\/body\s*>/i);
  return closingBody < 0 ? `${html}${liveReloadScript}` : `${html.slice(0, closingBody)}${liveReloadScript}${html.slice(closingBody)}`;
}

function contentType(filePath: string): string {
  return ({
    '.css': 'text/css; charset=utf-8',
    '.html': 'text/html; charset=utf-8',
    '.js': 'text/javascript; charset=utf-8',
    '.json': 'application/json; charset=utf-8',
    '.svg': 'image/svg+xml',
  } as Record<string, string>)[path.extname(filePath).toLowerCase()] ?? 'application/octet-stream';
}

async function serveFile(outputDir: string, request: IncomingMessage, response: ServerResponse): Promise<void> {
  const requested = decodeURIComponent((request.url ?? '/').split('?')[0]);
  const relative = requested === '/' ? 'index.html' : requested.replace(/^\/+/, '');
  const outputRoot = path.resolve(outputDir);
  const filePath = path.resolve(outputRoot, relative);
  if (filePath !== outputRoot && !filePath.startsWith(`${outputRoot}${path.sep}`)) {
    response.writeHead(403);
    response.end('Forbidden');
    return;
  }
  try {
    const file = await fs.readFile(filePath);
    const body = path.extname(filePath).toLowerCase() === '.html' ? injectLiveReload(file.toString()) : file;
    response.writeHead(200, { 'Content-Type': contentType(filePath) });
    response.end(body);
  } catch {
    response.writeHead(404);
    response.end('Not found');
  }
}

export async function startDevServer(options: ServeOptions = {}): Promise<DevServer> {
  const outputDir = path.resolve(options.outputDir ?? './dist');
  const contentDir = path.resolve(options.contentDir ?? './content');
  const templatesDir = path.resolve(options.templatesDir ?? './templates');
  await buildSite({ ...options, contentDir, outputDir, templatesDir });

  const clients = new Set<WebSocket>();
  const webSocketServer = new WebSocketServer({ noServer: true });
  webSocketServer.on('connection', (socket) => {
    clients.add(socket);
    socket.on('close', () => clients.delete(socket));
  });
  webSocketServer.on('close', () => clients.clear());
  const server = createServer((request, response) => {
    void serveFile(outputDir, request, response);
  });
  server.on('upgrade', (request, socket, head) => {
    if (request.url !== '/_ssg_live_reload') {
      socket.destroy();
      return;
    }
    webSocketServer.handleUpgrade(request, socket, head, (client) => webSocketServer.emit('connection', client, request));
  });
  const watcher = chokidar.watch([contentDir, templatesDir], { ignoreInitial: true });
  let rebuilding = false;
  let queued = false;
  const rebuild = async (): Promise<void> => {
    if (rebuilding) {
      queued = true;
      return;
    }
    rebuilding = true;
    try {
      await buildSite({ contentDir, outputDir, templatesDir });
      for (const client of clients) if (client.readyState === client.OPEN) client.send('reload');
    } catch (error: unknown) {
      console.error(error instanceof Error ? error.message : error);
    } finally {
      rebuilding = false;
      if (queued) {
        queued = false;
        void rebuild();
      }
    }
  };
  watcher.on('all', () => void rebuild());
  await new Promise<void>((resolve) => server.listen(options.port ?? 3000, 'localhost', resolve));
  return {
    server,
    watcher,
    close: async () => {
      await watcher.close();
      for (const client of clients) client.terminate();
      await new Promise<void>((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
      await new Promise<void>((resolve) => webSocketServer.close(() => resolve()));
    },
  };
}

export async function main(args = process.argv.slice(2)): Promise<void> {
  const options = parseArgs(args.slice(1));
  if (args[0] === 'build') await buildSite(options);
  else if (args[0] === 'serve') await startDevServer(options);
  else throw new Error('Usage: ssg build [--content <dir>] [--output <dir>] | ssg serve [--port <number>]');
}

if (require.main === module) {
  main().catch((error: unknown) => {
    console.error(error instanceof Error ? error.message : error);
    process.exitCode = 1;
  });
}
