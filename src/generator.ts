import { existsSync, mkdirSync, readdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { extname, join, relative, resolve } from 'node:path';
import { MarkdownPlugin } from '../plugins/MarkdownPlugin';
import { TemplatePlugin } from '../plugins/TemplatePlugin';
import type { BuildOptions as PluginBuildOptions, Plugin, PluginContext, SsgConfig } from './plugin';

export interface Page {
  title: string;
  date?: string;
  tags: string[];
  slug: string;
  html: string;
  template?: string;
  layout?: string;
}

export interface BuildOptions {
  contentDir?: string;
  outputDir?: string;
  templatesDir?: string;
  configPath?: string;
  port?: number;
  incremental?: boolean;
  clean?: boolean;
}

export interface BuildPipeline {
  build(): Page[];
  end(): Promise<void>;
  context: PluginContext;
}

interface CacheEntry {
  sourceHash: string;
  templateHash: string;
  renderDuration: number;
}

interface BuildCache {
  pages: Record<string, CacheEntry>;
}

const CACHE_FILE = '.ssg-cache.json';

function hash(value: string): string {
  return createHash('sha256').update(value).digest('hex');
}

function markdownFiles(directory: string): string[] {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) return markdownFiles(path);
    return entry.isFile() && ['.md', '.markdown'].includes(extname(entry.name).toLowerCase()) ? [path] : [];
  });
}

function templateHash(directory: string): string {
  if (!existsSync(directory)) return hash('');
  return hash(hbsFiles(directory).map((path) => `${relative(directory, path)}\0${readFileSync(path, 'utf8')}`).join('\0'));
}

function hbsFiles(directory: string): string[] {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) return hbsFiles(path);
    return entry.isFile() && extname(entry.name).toLowerCase() === '.hbs' ? [path] : [];
  }).sort();
}

function readCache(path: string): BuildCache | undefined {
  if (!existsSync(path)) return undefined;
  try {
    const cache = JSON.parse(readFileSync(path, 'utf8')) as BuildCache;
    return cache.pages && typeof cache.pages === 'object' ? cache : undefined;
  } catch {
    return undefined;
  }
}

function installTypeScriptLoader(): void {
  if (require.extensions['.ts']) return;
  require.extensions['.ts'] = (module, filename) => {
    const typescript = require('typescript') as typeof import('typescript');
    const source = readFileSync(filename, 'utf8');
    const output = typescript.transpileModule(source, { compilerOptions: { module: typescript.ModuleKind.CommonJS, target: typescript.ScriptTarget.ES2022, esModuleInterop: true } });
    module._compile(output.outputText, filename);
  };
}

export function loadPlugins(configPath?: string): Plugin[] {
  const path = resolve(configPath ?? 'ssg.config.ts');
  if (!existsSync(path)) return [MarkdownPlugin, TemplatePlugin];
  installTypeScriptLoader();
  delete require.cache[require.resolve(path)];
  const config = require(path) as SsgConfig | { default: SsgConfig };
  const loaded = 'default' in config ? config.default : config;
  return loaded.plugins ?? [MarkdownPlugin, TemplatePlugin];
}

function resolvedOptions(options: BuildOptions): PluginBuildOptions {
  return {
    contentDir: options.contentDir ?? './content',
    outputDir: options.outputDir ?? './dist',
    templatesDir: options.templatesDir ?? './templates',
    port: options.port,
  };
}

export function createBuildPipeline(options: BuildOptions = {}, command: 'build' | 'serve' = 'build'): BuildPipeline {
  const resolved = resolvedOptions(options);
  const plugins = loadPlugins(options.configPath);
  const cleanups: Array<() => Promise<void> | void> = [];
  let context: PluginContext;
  const build = (): Page[] => {
    if (!existsSync(resolved.contentDir)) throw new Error(`Content directory does not exist: ${resolved.contentDir}`);
    const cachePath = join(resolved.outputDir, CACHE_FILE);
    const previousCache = options.incremental && !options.clean ? readCache(cachePath) : undefined;
    const cleanBuild = !options.incremental || options.clean || !previousCache;
    if (cleanBuild) rmSync(resolved.outputDir, { recursive: true, force: true });
    mkdirSync(resolved.outputDir, { recursive: true });
    context.pages = [];
    context.stats = { pagesBuilt: 0, pagesSkipped: 0, timeSaved: 0 };
    for (const plugin of plugins) plugin.beforeBuild?.(context);
    const currentTemplateHash = templateHash(resolved.templatesDir);
    const cache: BuildCache = { pages: {} };
    for (const path of markdownFiles(resolved.contentDir)) {
      const relativePath = relative(resolved.contentDir, path).replace(/\.(md|markdown)$/i, '');
      const page: Page = { title: '', tags: [], slug: relativePath.replace(/\\/g, '/'), html: '' };
      const source = readFileSync(path, 'utf8');
      const sourceHash = hash(source);
      const outputPath = join(resolved.outputDir, `${relativePath}.html`);
      const cacheHit = previousCache?.pages[relativePath]?.sourceHash === sourceHash
        && previousCache.pages[relativePath].templateHash === currentTemplateHash
        && existsSync(outputPath);
      context.file = { path, source, outputPath, cacheHit };
      const startedAt = Date.now();
      for (const plugin of plugins) plugin.onFile?.(page, context);
      context.pages.push(page);
      const renderDuration = Date.now() - startedAt;
      cache.pages[relativePath] = { sourceHash, templateHash: currentTemplateHash, renderDuration: cacheHit ? previousCache?.pages[relativePath].renderDuration ?? 0 : renderDuration };
      if (cacheHit) {
        context.stats.pagesSkipped += 1;
        context.stats.timeSaved += previousCache?.pages[relativePath].renderDuration ?? 0;
      } else context.stats.pagesBuilt += 1;
    }
    context.file = undefined;
    context.pages.sort((a, b) => (b.date ?? '').localeCompare(a.date ?? ''));
    for (const plugin of plugins) plugin.afterBuild?.(context);
    writeFileSync(cachePath, JSON.stringify(cache, null, 2));
    return context.pages;
  };
  context = { options: resolved, command, pages: [], stats: { pagesBuilt: 0, pagesSkipped: 0, timeSaved: 0 }, rebuild: build, addCleanup: (cleanup) => cleanups.push(cleanup) };
  for (const plugin of plugins) plugin.onStart?.(context);
  return { build, context, end: async () => { for (const plugin of plugins) await plugin.onEnd?.(context); for (const cleanup of cleanups) await cleanup(); } };
}

export function buildSite(options: BuildOptions = {}): Page[] {
  const pipeline = createBuildPipeline(options);
  try {
    return pipeline.build();
  } finally {
    void pipeline.end();
  }
}

export { parsePage } from '../plugins/MarkdownPlugin';
