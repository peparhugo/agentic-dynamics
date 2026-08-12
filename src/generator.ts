import { access, mkdir, readFile, readdir, rm, writeFile } from 'node:fs/promises';
import path from 'node:path';
import Module from 'node:module';
import ts from 'typescript';
import { hashFile, hashText } from './cache';
import { MarkdownPlugin } from './plugins/markdown';
import { TemplatePlugin } from './plugins/template';
import type { Plugin, PluginConfig, PluginContext } from './plugin';

export interface PageMetadata { title?: string; date?: string; tags: string[]; [key: string]: unknown; }
export interface Page { sourcePath: string; outputPath: string; url: string; metadata: PageMetadata; content: string; }
export interface BuildOptions {
  contentDir?: string; outputDir?: string; templatesDir?: string; defaultTemplate?: string; defaultLayout?: string;
  plugins?: PluginConfig[]; configFile?: string; incremental?: boolean; clean?: boolean;
}
export interface BuildStats { built: number; skipped: number; timeSavedMs: number; }
export { Plugin, PluginConfig, PluginContext } from './plugin';

type Config = Partial<BuildOptions> & { plugins?: PluginConfig[] };
let tsLoaderInstalled = false;
let lastBuildStats: BuildStats = { built: 0, skipped: 0, timeSavedMs: 0 };

export function getLastBuildStats(): BuildStats { return { ...lastBuildStats }; }

interface CacheEntry {
  sourceHash: string;
  templateHash: string;
  outputPath: string;
  html: string;
  durationMs: number;
  page: { metadata: Page['metadata']; content: string; url: string };
}
interface CacheManifest {
  version: 1;
  templateHash: string;
  pages: Record<string, CacheEntry>;
}

async function templateHash(directory: string): Promise<string> {
  const files: string[] = [];
  const visit = async (current: string): Promise<void> => {
    let entries;
    try { entries = await readdir(current, { withFileTypes: true }); } catch { return; }
    for (const entry of entries) {
      const file = path.join(current, entry.name);
      if (entry.isDirectory()) await visit(file);
      else if (entry.isFile() && ['.hbs', '.ejs'].includes(path.extname(file).toLowerCase())) files.push(file);
    }
  };
  await visit(directory);
  const contents = await Promise.all(files.sort().map(async (file) => `${path.relative(directory, file)}\0${await hashFile(file)}`));
  return hashText(contents.join('\n'));
}

async function readManifest(file: string): Promise<CacheManifest | undefined> {
  try {
    const parsed = JSON.parse(await readFile(file, 'utf8')) as CacheManifest;
    return parsed.version === 1 && parsed.pages ? parsed : undefined;
  } catch { return undefined; }
}

function installTsLoader(): void {
  if (tsLoaderInstalled) return;
  tsLoaderInstalled = true;
  require.extensions['.ts'] = (module: NodeModule, filename: string) => {
    const source = require('node:fs').readFileSync(filename, 'utf8');
    (module as Module & { _compile: (code: string, file: string) => void })._compile(
      ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true } }).outputText,
      filename
    );
  };
}

async function loadConfig(file: string): Promise<Config> {
  try { await access(file); } catch { return {}; }
  installTsLoader();
  const loaded = require(file) as { default?: Config } & Config;
  return loaded.default || loaded;
}

async function resolvePlugins(configured: PluginConfig[], baseDirectory: string): Promise<Plugin[]> {
  const plugins: Plugin[] = [];
  for (const configuredPlugin of configured) {
    let plugin: Plugin | (() => Plugin | Promise<Plugin>) = configuredPlugin as Plugin;
    if (typeof configuredPlugin === 'string') {
      installTsLoader();
      const loaded = require(path.resolve(baseDirectory, configuredPlugin)) as { default?: Plugin };
      plugin = loaded.default || loaded;
    }
    if (typeof plugin === 'function') plugin = await plugin();
    plugins.push(plugin as Plugin);
  }
  return plugins;
}

export async function buildSite(options: BuildOptions = {}): Promise<Page[]> {
  const configPath = path.resolve(options.configFile || './ssg.config.ts');
  const config = await loadConfig(configPath);
  const merged: BuildOptions = {
    ...config,
    ...options,
    plugins: [...(config.plugins || []), ...(options.plugins || [])]
  };
  const context: PluginContext = {
    options: merged,
    contentDir: path.resolve(merged.contentDir || './content'),
    outputDir: path.resolve(merged.outputDir || './dist'),
    templatesDir: path.resolve(merged.templatesDir || './templates'),
    pages: [], files: new Map(), emitFile(filePath, contents) { this.files.set(filePath, contents); }
  };
  const manifestPath = path.join(context.outputDir, '.ssg-cache.json');
  const previous = merged.incremental && !merged.clean ? await readManifest(manifestPath) : undefined;
  const currentTemplateHash = await templateHash(context.templatesDir);
  const canUseCache = Boolean(previous && previous.templateHash === currentTemplateHash);
  context.cache = { parsed: new Map() };
  if (previous) {
    for (const [relative, entry] of Object.entries(previous!.pages)) context.cache.parsed.set(relative, {
      sourceHash: entry.sourceHash, metadata: entry.page.metadata, content: entry.page.content
    });
  }
  const plugins = [new MarkdownPlugin(), ...await resolvePlugins(merged.plugins || [], path.dirname(configPath)), new TemplatePlugin()];
  for (const plugin of plugins) await plugin.onStart?.(context);
  for (const plugin of plugins) await plugin.beforeBuild?.(context);
  const nextPages: Record<string, CacheEntry> = {};
  const stats: BuildStats = { built: 0, skipped: 0, timeSavedMs: 0 };
  for (let index = 0; index < context.pages.length; index += 1) {
    const originalPage = context.pages[index];
    const relative = path.relative(context.contentDir, originalPage.sourcePath);
    const sourceHash = await hashFile(originalPage.sourcePath);
    const cached = canUseCache ? previous!.pages[relative] : undefined;
    if (cached?.sourceHash === sourceHash && cached.templateHash === currentTemplateHash) {
      const cachedPage: Page = {
        sourcePath: originalPage.sourcePath, outputPath: cached.outputPath, url: cached.page.url,
        metadata: cached.page.metadata, content: cached.page.content
      };
      context.pages[index] = cachedPage;
      context.emitFile(cached.outputPath, cached.html);
      nextPages[relative] = cached;
      stats.skipped += 1;
      stats.timeSavedMs += cached.durationMs;
      continue;
    }
    const started = Date.now();
    let page = originalPage;
    for (const plugin of plugins) page = (await plugin.onFile?.(page, context)) || page;
    context.pages[index] = page;
    const html = context.files.get(page.outputPath);
    if (typeof html === 'string') nextPages[relative] = {
      sourceHash, templateHash: currentTemplateHash, outputPath: page.outputPath, html,
      durationMs: Date.now() - started,
      page: { metadata: page.metadata, content: page.content, url: page.url }
    };
    stats.built += 1;
  }
  if (!merged.incremental || merged.clean || !canUseCache) await rm(context.outputDir, { recursive: true, force: true });
  await mkdir(context.outputDir, { recursive: true });
  if (canUseCache) {
    for (const [relative, entry] of Object.entries(previous!.pages)) if (!nextPages[relative]) await rm(entry.outputPath, { force: true });
  }
  for (const plugin of plugins) await plugin.afterBuild?.(context);
  for (const [filePath, contents] of context.files) {
    await mkdir(path.dirname(filePath), { recursive: true });
    await writeFile(filePath, contents);
  }
  await writeFile(manifestPath, JSON.stringify({ version: 1, templateHash: currentTemplateHash, pages: nextPages }, null, 2));
  for (const plugin of plugins) await plugin.onEnd?.(context);
  lastBuildStats = stats;
  return context.pages;
}
