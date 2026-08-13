import { promises as fs } from 'node:fs';
import { createHash } from 'node:crypto';
import path from 'node:path';
import { loadConfig } from './config.js';
import type { Plugin } from './plugin.js';
import { MarkdownPlugin, parseMarkdownPage } from './plugins/markdown.js';
import { renderedPage, TemplatePlugin, type RenderedPage } from './plugins/template.js';

export type { Plugin, PluginHook, SsgConfig } from './plugin.js';
export { MarkdownPlugin } from './plugins/markdown.js';
export { TemplatePlugin } from './plugins/template.js';
export { DevServerPlugin } from './plugins/dev-server.js';

export interface Frontmatter {
  title?: string;
  date?: string;
  tags?: string[];
  template?: string;
  layout?: string | false;
  [key: string]: unknown;
}

export interface Page {
  title: string;
  date?: string;
  tags: string[];
  sourcePath: string;
  outputName: string;
  html: string;
  template?: string;
  layout?: string | false;
  data?: Frontmatter;
  /** Raw input available to file plugins until MarkdownPlugin processes it. */
  source?: string;
}

export interface BuildOptions {
  contentDir?: string;
  outputDir?: string;
  templatesDir?: string;
  configFile?: string;
  plugins?: Plugin[];
  incremental?: boolean;
  clean?: boolean;
  onBuildStats?: (stats: BuildStats) => void;
}

export interface BuildStats {
  pagesBuilt: number;
  pagesSkipped: number;
  timeSavedMs: number;
  durationMs: number;
}

export interface SsgEngine {
  build(): Promise<Page[]>;
  close(): Promise<void>;
}

interface CacheEntry {
  sourceHash: string;
  templateHash: string;
  outputName: string;
  page: Page;
  html: string;
  renderTimeMs: number;
}

interface CacheManifest {
  version: 1;
  pages: Record<string, CacheEntry>;
}

function hash(value: string): string {
  return createHash('sha256').update(value).digest('hex');
}

async function readManifest(filePath: string): Promise<CacheManifest | undefined> {
  try {
    const value = JSON.parse(await fs.readFile(filePath, 'utf8')) as CacheManifest;
    return value.version === 1 && value.pages && typeof value.pages === 'object' ? value : undefined;
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT' || error instanceof SyntaxError) return undefined;
    throw error;
  }
}

async function hashDirectory(directory: string): Promise<string> {
  try {
    const entries = await fs.readdir(directory, { withFileTypes: true });
    const values = await Promise.all(entries.sort((a, b) => a.name.localeCompare(b.name)).map(async (entry) => {
      const filePath = path.join(directory, entry.name);
      if (entry.isDirectory()) return `${entry.name}/${await hashDirectory(filePath)}`;
      if (entry.isFile()) return `${entry.name}:${hash(await fs.readFile(filePath, 'utf8'))}`;
      return entry.name;
    }));
    return hash(values.join('\n'));
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return hash('missing');
    throw error;
  }
}

async function templateFingerprint(page: Pick<Page, 'template' | 'layout'>, templatesDir: string, partialsHash: string): Promise<string> {
  const readTemplate = async (directory: string, name: string): Promise<string> => {
    const fileName = name.toLowerCase().endsWith('.hbs') ? name : `${name}.hbs`;
    try {
      return hash(await fs.readFile(path.resolve(directory, fileName), 'utf8'));
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code === 'ENOENT') return hash('missing');
      throw error;
    }
  };
  const templateHash = await readTemplate(templatesDir, page.template ?? 'default');
  const layoutHash = page.layout === false
    ? 'disabled'
    : await readTemplate(path.join(templatesDir, 'layouts'), page.layout ?? 'default');
  return hash(`${templateHash}:${layoutHash}:${partialsHash}`);
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function formatDate(value: string | undefined): string | undefined {
  if (!value) return undefined;
  const match = /^(\d{4})-(\d{2})-(\d{2})(?:T.*)?$/.exec(value);
  if (!match) return value;
  const date = new Date(Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3])));
  return new Intl.DateTimeFormat('en-US', {
    year: 'numeric', month: 'long', day: 'numeric', timeZone: 'UTC',
  }).format(date);
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

export function parsePage(source: string, sourcePath: string): Page {
  return parseMarkdownPage(source, sourcePath);
}

export function renderPage(page: Page): string {
  const metadata = [
    page.date ? `<time datetime="${escapeHtml(page.date)}">${escapeHtml(formatDate(page.date) ?? page.date)}</time>` : '',
    page.tags.length > 0 ? `<p class="tags">${page.tags.map(escapeHtml).join(', ')}</p>` : '',
  ].filter(Boolean).join('\n');
  return document(page.title, `<main>
  <article>
    <h1>${escapeHtml(page.title)}</h1>
    ${metadata}
    ${page.html}
  </article>
</main>`);
}

export function renderIndex(pages: Page[]): string {
  const items = pages.map((page) => {
    const date = page.date ? ` <time datetime="${escapeHtml(page.date)}">${escapeHtml(formatDate(page.date) ?? page.date)}</time>` : '';
    return `    <li><a href="${encodeURIComponent(page.outputName)}">${escapeHtml(page.title)}</a>${date}</li>`;
  }).join('\n');
  return document('Pages', `<main>
  <h1>Pages</h1>
  <ul>
${items}
  </ul>
</main>`);
}

async function runHook(plugins: Plugin[], hook: keyof Plugin, page?: Page): Promise<void> {
  for (const plugin of plugins) {
    const handler = plugin[hook];
    if (typeof handler === 'function') {
      await (handler as (page?: Page) => void | Promise<void>).call(plugin, page);
    }
  }
}

export function createSsg(options: BuildOptions = {}): SsgEngine {
  const contentDir = path.resolve(options.contentDir ?? './content');
  const outputDir = path.resolve(options.outputDir ?? './dist');
  const templatesDir = path.resolve(options.templatesDir ?? './templates');
  const configured = options.plugins ?? loadConfig(options.configFile).plugins ?? [];
  const plugins: Plugin[] = [new MarkdownPlugin(), ...configured, new TemplatePlugin(templatesDir)];
  const cacheFile = path.join(path.dirname(contentDir), '.ssg-cache.json');
  let started = false;
  let closed = false;

  return {
    async build(): Promise<Page[]> {
      const buildStarted = performance.now();
      if (closed) throw new Error('SSG engine is closed');
      if (!started) {
        await runHook(plugins, 'onStart');
        started = true;
      }
      await runHook(plugins, 'beforeBuild');
      if (options.clean) await fs.rm(outputDir, { recursive: true, force: true });
      const useCache = options.incremental === true && !options.clean;
      const previousManifest = useCache ? await readManifest(cacheFile) : undefined;
      const partialsHash = await hashDirectory(path.join(templatesDir, 'partials'));
      const entries = await fs.readdir(contentDir, { withFileTypes: true });
      const markdownFiles = entries
        .filter((entry) => entry.isFile() && /\.md$/i.test(entry.name))
        .map((entry) => entry.name)
        .sort();
      const pages: Page[] = [];
      const manifest: CacheManifest = { version: 1, pages: {} };
      const entriesToWrite: CacheEntry[] = [];
      let pagesBuilt = 0;
      let pagesSkipped = 0;
      let timeSavedMs = 0;
      for (const fileName of markdownFiles) {
        const sourcePath = path.join(contentDir, fileName);
        const source = await fs.readFile(sourcePath, 'utf8');
        const sourceHash = hash(source);
        const cached = previousManifest?.pages[fileName];
        const cachedTemplateHash = cached
          ? await templateFingerprint(cached.page, templatesDir, partialsHash)
          : undefined;
        const outputExists = cached
          ? await fs.access(path.join(outputDir, cached.outputName)).then(() => true, () => false)
          : false;
        if (cached && cached.sourceHash === sourceHash && cached.templateHash === cachedTemplateHash && outputExists) {
          const page = { ...cached.page, tags: [...cached.page.tags], data: cached.page.data ? { ...cached.page.data } : undefined };
          pages.push(page);
          manifest.pages[fileName] = cached;
          pagesSkipped += 1;
          timeSavedMs += cached.renderTimeMs;
          continue;
        }
        const page: Page = {
          title: path.basename(fileName, path.extname(fileName)),
          tags: [],
          sourcePath,
          outputName: '',
          html: '',
          source,
        };
        const pageStarted = performance.now();
        await runHook(plugins, 'onFile', page);
        const renderedHtml = (page as RenderedPage)[renderedPage] ?? renderPage(page);
        const renderTimeMs = performance.now() - pageStarted;
        const storedPage = { ...page } as Page;
        delete storedPage.source;
        pages.push(page);
        const entry: CacheEntry = {
          sourceHash,
          templateHash: await templateFingerprint(page, templatesDir, partialsHash),
          outputName: page.outputName,
          page: storedPage,
          html: renderedHtml,
          renderTimeMs,
        };
        manifest.pages[fileName] = entry;
        entriesToWrite.push(entry);
        pagesBuilt += 1;
      }
      pages.sort((a, b) => (b.date ?? '').localeCompare(a.date ?? '') || a.title.localeCompare(b.title));
      await fs.mkdir(outputDir, { recursive: true });
      await Promise.all(entriesToWrite.map((entry) => fs.writeFile(
        path.join(outputDir, entry.outputName), entry.html, 'utf8',
      )));
      if (previousManifest) {
        await Promise.all(Object.entries(previousManifest.pages)
          .filter(([fileName]) => !manifest.pages[fileName])
          .map(([, entry]) => fs.rm(path.join(outputDir, entry.outputName), { force: true })));
      }
      await fs.writeFile(path.join(outputDir, 'index.html'), renderIndex(pages), 'utf8');
      await fs.writeFile(cacheFile, `${JSON.stringify(manifest, null, 2)}\n`, 'utf8');
      await runHook(plugins, 'afterBuild');
      options.onBuildStats?.({
        pagesBuilt,
        pagesSkipped,
        timeSavedMs,
        durationMs: performance.now() - buildStarted,
      });
      return pages;
    },
    async close(): Promise<void> {
      if (closed) return;
      closed = true;
      if (started) await runHook(plugins, 'onEnd');
    },
  };
}

export async function buildSite(options: BuildOptions = {}): Promise<Page[]> {
  const ssg = createSsg(options);
  try {
    return await ssg.build();
  } finally {
    await ssg.close();
  }
}
