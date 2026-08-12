import { promises as fs } from 'node:fs';
import crypto from 'node:crypto';
import path from 'node:path';
import { BuildOptions, BuildStats, Frontmatter, Page } from './types';
import { Plugin, PluginContext } from './plugin';
import { MarkdownPlugin, markdownFiles, parseMarkdown } from './markdown-plugin';
import { TemplatePlugin } from './template-plugin';
import { loadConfiguredPlugins } from './config';

const DEFAULT_CONTENT_DIR = './content';
const DEFAULT_OUTPUT_DIR = './dist';
const DEFAULT_TEMPLATES_DIR = './templates';
const CACHE_FILE = '.ssg-cache.json';

interface CachePage {
  sourceHash: string;
  templateHash: string;
  outputPath: string;
  frontmatter: Frontmatter;
  html: string;
  renderTimeMs: number;
}

interface BuildCache {
  version: 1;
  templateHash: string;
  pages: Record<string, CachePage>;
}

function escapeHtml(value: string): string {
  return value.replace(/[&<>"']/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[character] as string));
}

function pageDocument(page: Page): string {
  return `<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n<title>${escapeHtml(page.frontmatter.title)}</title>\n</head>\n<body>\n<main>\n<h1>${escapeHtml(page.frontmatter.title)}</h1>\n${page.frontmatter.date ? `<time datetime="${escapeHtml(page.frontmatter.date)}">${escapeHtml(page.frontmatter.date)}</time>\n` : ''}${page.html}</main>\n</body>\n</html>\n`;
}

function indexDocument(pages: Page[]): string {
  const items = pages.map((page) => {
    const metadata = [page.frontmatter.date, ...page.frontmatter.tags].filter(Boolean).map(escapeHtml).join(' | ');
    return `<li><a href="${encodeURI(page.outputPath)}">${escapeHtml(page.frontmatter.title)}</a>${metadata ? ` <small>${metadata}</small>` : ''}</li>`;
  }).join('\n');
  return `<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n<title>Home</title>\n</head>\n<body>\n<main>\n<h1>Pages</h1>\n<ul>\n${items}\n</ul>\n</main>\n</body>\n</html>\n`;
}

async function runHook(plugins: Plugin[], hook: 'onStart' | 'beforeBuild' | 'afterBuild' | 'onEnd', context: PluginContext): Promise<void> {
  for (const plugin of plugins) if (plugin[hook]) await plugin[hook]!(context);
}

async function hashFiles(directory: string): Promise<string> {
  const files: string[] = [];
  async function collect(current: string): Promise<void> {
    let entries: import('node:fs').Dirent[];
    try { entries = await fs.readdir(current, { withFileTypes: true }); } catch { return; }
    for (const entry of entries) {
      const file = path.join(current, entry.name);
      if (entry.isDirectory()) await collect(file);
      else if (entry.isFile()) files.push(file);
    }
  }
  await collect(directory);
  files.sort();
  const hash = crypto.createHash('sha256');
  for (const file of files) {
    hash.update(path.relative(directory, file).replace(/\\/g, '/'));
    hash.update(await fs.readFile(file));
  }
  return hash.digest('hex');
}

function contentHash(content: string): string {
  return crypto.createHash('sha256').update(content).digest('hex');
}

async function readCache(file: string): Promise<BuildCache | undefined> {
  try {
    const cache = JSON.parse(await fs.readFile(file, 'utf8')) as BuildCache;
    return cache.version === 1 && cache.pages ? cache : undefined;
  } catch { return undefined; }
}

export async function buildSite(options: BuildOptions = {}): Promise<Page[]> {
  const startedAt = Date.now();
  const contentDir = path.resolve(options.contentDir || DEFAULT_CONTENT_DIR);
  const outputDir = path.resolve(options.outputDir || DEFAULT_OUTPUT_DIR);
  const templatesDir = path.resolve(options.templatesDir || DEFAULT_TEMPLATES_DIR);
  const cacheFile = path.join(outputDir, CACHE_FILE);
  if (options.clean) await fs.rm(outputDir, { recursive: true, force: true });
  const incremental = options.incremental === true;
  const templateHash = incremental ? await hashFiles(templatesDir) : '';
  const oldCache = incremental && !options.clean ? await readCache(cacheFile) : undefined;
  const canUseCache = Boolean(oldCache && oldCache.templateHash === templateHash);
  const context: PluginContext = { options, contentDir, outputDir, templatesDir, pages: [] };
  const configured = await loadConfiguredPlugins(options.configFile, context, options.plugins);
  const plugins = [new MarkdownPlugin(), ...configured, new TemplatePlugin()];
  await runHook(plugins, 'onStart', context);
  await runHook(plugins, 'beforeBuild', context);
  const files = await markdownFiles(contentDir);
  let pagesBuilt = 0;
  let pagesSkipped = 0;
  let timeSavedMs = 0;
  const newCache: BuildCache = { version: 1, templateHash, pages: {} };
  for (const file of files) {
    const source = await fs.readFile(file, 'utf8');
    const key = path.relative(contentDir, file).replace(/\\/g, '/');
    const sourceHash = contentHash(source);
    const cached = canUseCache ? oldCache!.pages[key] : undefined;
    let page: Page;
    if (cached && cached.sourceHash === sourceHash) {
      page = { sourcePath: file, outputPath: cached.outputPath, slug: cached.outputPath.replace(/\.html$/, ''), frontmatter: cached.frontmatter, html: cached.html };
      pagesSkipped += 1;
      timeSavedMs += cached.renderTimeMs;
    } else {
      const renderStartedAt = Date.now();
      page = { sourcePath: file, outputPath: '', slug: '', frontmatter: { title: '', tags: [] }, html: source };
      for (const plugin of plugins) if (plugin.onFile) page = (await plugin.onFile(page, context)) || page;
      pagesBuilt += 1;
      newCache.pages[key] = { sourceHash, templateHash, outputPath: page.outputPath, frontmatter: page.frontmatter, html: page.html, renderTimeMs: Date.now() - renderStartedAt };
    }
    if (!newCache.pages[key]) newCache.pages[key] = { sourceHash, templateHash, outputPath: page.outputPath, frontmatter: page.frontmatter, html: page.html, renderTimeMs: cached?.renderTimeMs || 0 };
    context.pages.push(page);
  }
  context.pages.sort((a, b) => a.slug.localeCompare(b.slug));
  await fs.mkdir(outputDir, { recursive: true });
  await Promise.all(context.pages.map(async (page) => {
    const destination = path.join(outputDir, page.outputPath);
    await fs.mkdir(path.dirname(destination), { recursive: true });
    await fs.writeFile(destination, page.html === '' ? pageDocument(page) : page.html, 'utf8');
  }));
  await fs.writeFile(path.join(outputDir, 'index.html'), indexDocument(context.pages), 'utf8');
  if (incremental) {
    if (oldCache) {
      const currentKeys = new Set(Object.keys(newCache.pages));
      await Promise.all(Object.entries(oldCache.pages).filter(([key]) => !currentKeys.has(key)).map(async ([, page]) => {
        await fs.rm(path.join(outputDir, page.outputPath), { force: true });
      }));
    }
    await fs.writeFile(cacheFile, JSON.stringify(newCache, null, 2), 'utf8');
  }
  await runHook(plugins, 'afterBuild', context);
  await runHook(plugins, 'onEnd', context);
  const stats: BuildStats = { pagesBuilt, pagesSkipped, timeSavedMs, durationMs: Date.now() - startedAt };
  options.onStats?.(stats);
  return context.pages;
}

export { escapeHtml, indexDocument, pageDocument, parseMarkdown };
