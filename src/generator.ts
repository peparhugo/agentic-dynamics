import { promises as fs } from 'node:fs';
import { createHash } from 'node:crypto';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { MarkdownPlugin } from '../plugins/markdown.js';
import { TemplatePlugin } from '../plugins/template.js';
import type { BuildContext, BuildStats, Page, Plugin, SourcePage } from '../plugins/types.js';

export type { BuildStats, Page, Plugin } from '../plugins/types.js';

export interface BuildOptions {
  contentDir?: string;
  outputDir?: string;
  templatesDir?: string;
  plugins?: Plugin[];
  incremental?: boolean;
  clean?: boolean;
  onBuildComplete?: (stats: BuildStats) => void;
}

interface CacheManifest {
  version: 1;
  sourceHashes: Record<string, string>;
  templateHash: string;
  sourcePages: Record<string, SourcePage>;
  averagePageBuildMs: number;
}

const CACHE_FILE = '.ssg-cache.json';

function hash(content: string): string {
  return createHash('sha256').update(content).digest('hex');
}

async function filesIn(directory: string): Promise<string[]> {
  try {
    const entries = await fs.readdir(directory, { withFileTypes: true });
    const nested = await Promise.all(entries.map(async (entry) => {
      const entryPath = path.join(directory, entry.name);
      if (entry.isDirectory()) return filesIn(entryPath).then((files) => files.map((file) => path.join(entry.name, file)));
      return entry.isFile() ? [entry.name] : [];
    }));
    return nested.flat();
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return [];
    throw error;
  }
}

async function readCache(file: string): Promise<CacheManifest | undefined> {
  try {
    const cache = JSON.parse(await fs.readFile(file, 'utf8')) as CacheManifest;
    return cache.version === 1 ? cache : undefined;
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT' || error instanceof SyntaxError) return undefined;
    throw error;
  }
}

async function templateHash(directory: string): Promise<string> {
  const files = await filesIn(directory);
  const content = await Promise.all(files.sort().map(async (file) => `${file}\0${await fs.readFile(path.join(directory, file), 'utf8')}`));
  return hash(content.join('\0'));
}

export interface SsgConfig {
  plugins?: Plugin[];
}

async function loadConfig(): Promise<SsgConfig> {
  const file = path.resolve('./ssg.config.ts');
  try {
    await fs.access(file);
    const config = await import(pathToFileURL(file).href);
    return (config.default ?? config) as SsgConfig;
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return {};
    throw error;
  }
}

async function runHook(plugins: Plugin[], hook: keyof Plugin, context: BuildContext): Promise<void> {
  for (const plugin of plugins) {
    if (hook === 'onStart') await plugin.onStart?.(context);
    if (hook === 'beforeBuild') await plugin.beforeBuild?.(context);
    if (hook === 'afterBuild') await plugin.afterBuild?.(context);
    if (hook === 'onEnd') await plugin.onEnd?.(context);
  }
}

export async function buildSite(options: BuildOptions = {}): Promise<Page[]> {
  const startedAt = Date.now();
  const config = await loadConfig();
  const contentDir = path.resolve(options.contentDir ?? './content');
  const outputDir = path.resolve(options.outputDir ?? './site');
  const templatesDir = path.resolve(options.templatesDir ?? './templates');
  const cacheFile = path.join(outputDir, CACHE_FILE);
  const cache = options.clean ? undefined : await readCache(cacheFile);
  const cleanBuild = Boolean(options.clean || !cache);
  const entries = await fs.readdir(contentDir, { withFileTypes: true });
  const files = entries.filter((entry) => entry.isFile() && /\.md$/i.test(entry.name)).map((entry) => entry.name).sort();
  const sourceHashes = Object.fromEntries(await Promise.all(files.map(async (file) => [file, hash(await fs.readFile(path.join(contentDir, file), 'utf8'))])));
  const currentTemplateHash = await templateHash(templatesDir);
  const templateChanged = !cache || cache.templateHash !== currentTemplateHash;
  const removedFiles = cache && Object.keys(cache.sourceHashes).some((file) => !files.includes(file));
  const filesToBuild = new Set(files.filter((file) => !options.incremental || !cache || templateChanged || cache.sourceHashes[file] !== sourceHashes[file]));
  if (cleanBuild) await fs.rm(outputDir, { recursive: true, force: true });
  if (cache && !cleanBuild) {
    await Promise.all(Object.keys(cache.sourceHashes)
      .filter((file) => !files.includes(file))
      .map((file) => fs.rm(path.join(outputDir, `${path.basename(file, path.extname(file))}.html`), { force: true })));
  }
  const context: BuildContext = {
    contentDir,
    outputDir,
    templatesDir,
    files,
    sourcePages: [],
    pages: [],
    incremental: Boolean(options.incremental),
    clean: cleanBuild,
    sourceHashes,
    templateHash: currentTemplateHash,
    cachedSourcePages: options.incremental && cache ? cache.sourcePages : {},
    filesToBuild,
    shouldBuildIndex: !options.incremental || !cache || templateChanged || removedFiles || filesToBuild.size > 0,
    stats: { pagesBuilt: filesToBuild.size, pagesSkipped: files.length - filesToBuild.size, timeSavedMs: 0, durationMs: 0 },
  };
  const plugins = [new MarkdownPlugin(), ...(config.plugins ?? []), ...(options.plugins ?? []), new TemplatePlugin()];
  await runHook(plugins, 'onStart', context);
  try {
    await runHook(plugins, 'beforeBuild', context);
    for (const page of context.sourcePages) {
      if (!context.filesToBuild.has(`${page.slug}.md`)) continue;
      for (const plugin of plugins) await plugin.onFile?.(page, context);
    }
    await runHook(plugins, 'afterBuild', context);
    context.stats.durationMs = Date.now() - startedAt;
    context.stats.timeSavedMs = Math.round(context.stats.pagesSkipped * (cache?.averagePageBuildMs ?? 0));
    await fs.writeFile(cacheFile, JSON.stringify({
      version: 1,
      sourceHashes: context.sourceHashes,
      templateHash: context.templateHash,
      sourcePages: Object.fromEntries(context.sourcePages.map((page) => [`${page.slug}.md`, page])),
      averagePageBuildMs: context.stats.pagesBuilt > 0 ? context.stats.durationMs / context.stats.pagesBuilt : cache?.averagePageBuildMs ?? 0,
    }, null, 2));
    options.onBuildComplete?.(context.stats);
    return context.pages;
  } finally {
    await runHook(plugins, 'onEnd', context);
  }
}
