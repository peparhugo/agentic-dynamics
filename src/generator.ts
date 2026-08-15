import { mkdir, readdir, readFile, rm, writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { dirname, join, resolve } from 'node:path';
import { Plugin, PluginContext, SsgConfig } from './plugin';
import { MarkdownPlugin, parsePage as parseMarkdownPage } from './plugins/markdown';
import { TemplatePlugin } from './plugins/template';

export interface Page { sourcePath: string; outputPath: string; slug: string; title: string; date?: string; tags: string[]; html: string; template?: string; layout?: string; }
export interface BuildOptions { contentDir?: string; outputDir?: string; templateDir?: string; plugins?: Plugin[]; configFile?: string; incremental?: boolean; clean?: boolean; }
export interface BuildStats { pagesBuilt: number; pagesSkipped: number; timeSavedMs: number; }
export interface BuildResult { pages: Page[]; stats: BuildStats; }
type Frontmatter = Record<string, string | string[]>;
interface CacheEntry { sourceHash: string; templateHash: string; page: Page; parsedPage: Page; renderedHtml: string; renderTimeMs: number; }
interface BuildCache { version: 1; pages: Record<string, CacheEntry>; }
const cacheFilename = '.ssg-cache.json';

function parseYamlValue(value: string): string | string[] { const trimmed = value.trim(); return trimmed.startsWith('[') && trimmed.endsWith(']') ? trimmed.slice(1, -1).split(',').map((item) => item.trim().replace(/^['"]|['"]$/g, '')).filter(Boolean) : trimmed.replace(/^['"]|['"]$/g, ''); }
export function parseYamlFrontmatter(source: string): { data: Frontmatter; content: string } {
  const match = source.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n?/);
  if (!match) return { data: {}, content: source };
  const data: Frontmatter = {};
  for (const line of match[1].split(/\r?\n/)) { const separator = line.indexOf(':'); if (separator > 0) { const key = line.slice(0, separator).trim(); if (key) data[key] = parseYamlValue(line.slice(separator + 1)); } }
  return { data, content: source.slice(match[0].length) };
}
export const parsePage = parseMarkdownPage;

async function markdownFiles(directory: string): Promise<string[]> {
  const entries = await readdir(directory, { withFileTypes: true });
  return (await Promise.all(entries.map((entry) => { const path = join(directory, entry.name); return entry.isDirectory() ? markdownFiles(path) : entry.isFile() && /\.md$/i.test(entry.name) ? Promise.resolve([path]) : Promise.resolve([]); }))).flat();
}

function hash(value: string): string { return createHash('sha256').update(value).digest('hex'); }

async function templateHash(directory: string): Promise<string> {
  async function files(path: string): Promise<string[]> {
    try {
      const entries = await readdir(path, { withFileTypes: true });
      return (await Promise.all(entries.map((entry) => {
        const entryPath = join(path, entry.name);
        return entry.isDirectory() ? files(entryPath) : entry.isFile() && /\.hbs$/i.test(entry.name) ? Promise.resolve([entryPath]) : Promise.resolve([]);
      }))).flat();
    } catch (error: unknown) {
      if ((error as NodeJS.ErrnoException).code === 'ENOENT') return [];
      throw error;
    }
  }
  const paths = (await files(directory)).sort();
  return hash(await Promise.all(paths.map(async (path) => `${path.slice(directory.length)}:${await readFile(path, 'utf8')}`)).then((parts) => parts.join('\n')));
}

async function readCache(path: string): Promise<BuildCache | undefined> {
  try {
    const cache = JSON.parse(await readFile(path, 'utf8')) as BuildCache;
    return cache && cache.version === 1 && cache.pages ? cache : undefined;
  } catch (error: unknown) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT' || error instanceof SyntaxError) return undefined;
    throw error;
  }
}

function copyPage(page: Page): Page { return { ...page, tags: [...page.tags] }; }

function loadConfig(configFile?: string): Plugin[] {
  const path = resolve(configFile ?? 'ssg.config.ts');
  try {
    // Node cannot execute TypeScript configuration files without this loader.
    if (path.endsWith('.ts') && !require.extensions['.ts']) {
      require.extensions['.ts'] = (module: NodeModule, filename: string) => {
        const typescript = require('typescript') as typeof import('typescript');
        const source = require('node:fs').readFileSync(filename, 'utf8') as string;
        (module as NodeModule & { _compile(source: string, filename: string): void })._compile(typescript.transpileModule(source, { compilerOptions: { module: typescript.ModuleKind.CommonJS, target: typescript.ScriptTarget.ES2022, esModuleInterop: true } }).outputText, filename);
      };
    }
    const config = require(path) as SsgConfig | { default?: SsgConfig };
    return (('default' in config ? config.default : config)?.plugins) ?? [];
  } catch (error: unknown) {
    if ((error as NodeJS.ErrnoException).code === 'MODULE_NOT_FOUND' && (error as NodeJS.ErrnoException).message.includes(path)) return [];
    throw error;
  }
}

async function runHook(plugins: Plugin[], hook: keyof Plugin, context: PluginContext, page?: Page): Promise<void> {
  for (const plugin of plugins) {
    const handler = plugin[hook];
    if (!handler) continue;
    if (hook === 'onFile' && page) await (handler as NonNullable<Plugin['onFile']>)(page, context);
    else await (handler as (context: PluginContext) => void | Promise<void>)(context);
  }
}

export async function buildSite(options: BuildOptions = {}): Promise<Page[]> {
  return (await buildSiteWithStats(options)).pages;
}

export async function buildSiteWithStats(options: BuildOptions = {}): Promise<BuildResult> {
  const context: PluginContext = { contentDir: resolve(options.contentDir ?? 'content'), outputDir: resolve(options.outputDir ?? 'dist'), templateDir: resolve(options.templateDir ?? 'templates'), pages: [], sources: new Map(), renderedPages: new Map(), parsedPages: new Map() };
  const pagePlugins = [...loadConfig(options.configFile), ...(options.plugins ?? [])];
  const plugins = [MarkdownPlugin, ...pagePlugins, TemplatePlugin];
  const cachePath = join(context.outputDir, cacheFilename);
  const existingCache = options.incremental && !options.clean ? await readCache(cachePath) : undefined;
  const shouldClean = options.clean || !existingCache;
  const currentTemplateHash = await templateHash(context.templateDir);
  const stats: BuildStats = { pagesBuilt: 0, pagesSkipped: 0, timeSavedMs: 0 };
  await runHook(plugins, 'onStart', context);
  try {
    await runHook(plugins, 'beforeBuild', context);
    const files = await markdownFiles(context.contentDir);
    const nextCache: BuildCache = { version: 1, pages: {} };
    for (const sourcePath of files) {
      const source = await readFile(sourcePath, 'utf8');
      const sourceHash = hash(source);
      const cached = existingCache?.pages[sourcePath];
      if (cached && cached.sourceHash === sourceHash && cached.templateHash === currentTemplateHash) {
        const page = copyPage(cached.page);
        context.pages.push(page);
        context.renderedPages.set(page.outputPath, cached.renderedHtml);
        nextCache.pages[sourcePath] = cached;
        stats.pagesSkipped += 1;
        stats.timeSavedMs += cached.renderTimeMs;
        continue;
      }
      context.sources.set(sourcePath, source);
      const page = { sourcePath, outputPath: '', slug: '', title: '', tags: [], html: '' };
      if (cached && cached.sourceHash === sourceHash && cached.parsedPage) context.parsedPages.set(sourcePath, copyPage(cached.parsedPage));
      context.pages.push(page);
      const startedAt = Date.now();
      await MarkdownPlugin.onFile?.(page, context);
      const parsedPage = copyPage(page);
      await runHook([...pagePlugins, TemplatePlugin], 'onFile', context, page);
      const renderTimeMs = Date.now() - startedAt;
      nextCache.pages[sourcePath] = { sourceHash, templateHash: currentTemplateHash, page: copyPage(page), parsedPage, renderedHtml: context.renderedPages.get(page.outputPath) ?? page.html, renderTimeMs };
      stats.pagesBuilt += 1;
    }
    context.pages.sort((a, b) => a.title.localeCompare(b.title));
    if (shouldClean) await rm(context.outputDir, { recursive: true, force: true });
    await mkdir(context.outputDir, { recursive: true });
    await Promise.all(context.pages.map(async (page) => { await mkdir(dirname(page.outputPath), { recursive: true }); await writeFile(page.outputPath, context.renderedPages.get(page.outputPath) ?? page.html, 'utf8'); }));
    await runHook(plugins, 'afterBuild', context);
    await writeFile(cachePath, JSON.stringify(nextCache), 'utf8');
    return { pages: context.pages, stats };
  } finally { await runHook(plugins, 'onEnd', context); }
}
