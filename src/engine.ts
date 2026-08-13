import { existsSync, readFileSync } from 'node:fs';
import { mkdir, readdir, readFile, rm, unlink, writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { dirname, extname, join, resolve } from 'node:path';
import type { BuildOptions, BuildStats, Page } from './generator';
import { MarkdownPlugin, TemplatePlugin, type Plugin, type PluginContext, type PluginFile } from './plugins';

async function markdownFiles(directory: string): Promise<string[]> {
  const entries = await readdir(directory, { withFileTypes: true });
  const files = await Promise.all(entries.map(async (entry) => {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) return markdownFiles(path);
    return ['.md', '.markdown'].includes(extname(entry.name).toLowerCase()) ? [path] : [];
  }));
  return files.flat();
}

const cacheFileName = '.ssg-cache.json';

interface CachedPage extends Page {
  sourceHash: string;
  output?: string;
  data: Record<string, unknown>;
  renderMs: number;
}

interface BuildCache {
  version: 1;
  templateHash: string;
  pages: Record<string, CachedPage>;
}

const hash = (value: string): string => createHash('sha256').update(value).digest('hex');

async function directoryHash(directory: string): Promise<string> {
  if (!existsSync(directory)) return hash('');
  const files = await templateFiles(directory);
  return hash((await Promise.all(files.sort().map(async (file) => `${file}\0${await readFile(file, 'utf8')}`))).join('\0'));
}

async function templateFiles(directory: string): Promise<string[]> {
  const entries = await readdir(directory, { withFileTypes: true });
  const files = await Promise.all(entries.map(async (entry) => {
    const path = join(directory, entry.name);
    return entry.isDirectory() ? templateFiles(path) : [path];
  }));
  return files.flat();
}

async function loadCache(path: string): Promise<BuildCache | undefined> {
  try {
    const cache = JSON.parse(await readFile(path, 'utf8')) as BuildCache;
    return cache.version === 1 && typeof cache.templateHash === 'string' && cache.pages !== undefined ? cache : undefined;
  } catch {
    return undefined;
  }
}

async function loadConfiguredPlugins(): Promise<Plugin[]> {
  const configPath = resolve('ssg.config.ts');
  if (!existsSync(configPath)) return [];

  // TypeScript configs and their local plugin imports are transpiled on demand.
  const typescript = await import('typescript');
  const previous = require.extensions['.ts'];
  require.extensions['.ts'] = (module, filename) => {
    const source = readFileSync(filename, 'utf8');
    const output = typescript.transpileModule(source, { compilerOptions: { module: typescript.ModuleKind.CommonJS, target: typescript.ScriptTarget.ES2022 } });
    module._compile(output.outputText, filename);
  };
  try {
    delete require.cache[configPath];
    const config = require(configPath) as { default?: Plugin[]; plugins?: Plugin[] };
    const plugins = config.default ?? config.plugins ?? [];
    if (!Array.isArray(plugins)) throw new Error('ssg.config.ts must export a plugin array or { plugins: Plugin[] }');
    return plugins;
  } finally {
    if (previous === undefined) delete require.extensions['.ts'];
    else require.extensions['.ts'] = previous;
  }
}

export class SsgEngine {
  lastBuildStats: BuildStats = { pagesBuilt: 0, pagesSkipped: 0, timeSavedMs: 0 };

  constructor(private readonly plugins: Plugin[]) {}

  async build(options: BuildOptions = {}): Promise<Page[]> {
    const resolvedOptions: Required<BuildOptions> = {
      contentDir: options.contentDir ?? './content',
      outputDir: options.outputDir ?? './dist',
      templateDir: options.templateDir ?? './templates',
      incremental: options.incremental ?? false,
      clean: options.clean ?? false,
    };
    if (!existsSync(resolvedOptions.contentDir)) throw new Error(`Content directory does not exist: ${resolvedOptions.contentDir}`);
    const context: PluginContext = { options: resolvedOptions, pages: [] };
    await this.run('onStart', context);
    try {
      await this.run('beforeBuild', context);
      const files = await markdownFiles(resolvedOptions.contentDir);
      const cachePath = join(resolvedOptions.outputDir, cacheFileName);
      const previousCache = resolvedOptions.incremental && !resolvedOptions.clean ? await loadCache(cachePath) : undefined;
      const templateHash = await directoryHash(resolvedOptions.templateDir);
      const canIncrement = previousCache !== undefined && previousCache.templateHash === templateHash;
      if (!canIncrement || resolvedOptions.clean || !resolvedOptions.incremental) await rm(resolvedOptions.outputDir, { recursive: true, force: true });
      await mkdir(resolvedOptions.outputDir, { recursive: true });
      const cache: BuildCache = { version: 1, templateHash, pages: {} };
      let pagesBuilt = 0;
      let pagesSkipped = 0;
      let timeSavedMs = 0;
      for (const source of files) {
        const sourceContent = await readFile(source, 'utf8');
        const sourceHash = hash(sourceContent);
        const cached = canIncrement ? previousCache?.pages[source] : undefined;
        if (cached?.sourceHash === sourceHash) {
          const destination = join(resolvedOptions.outputDir, cached.slug);
          if (cached.output !== undefined && !existsSync(destination)) {
            await mkdir(dirname(destination), { recursive: true });
            await writeFile(destination, cached.output, 'utf8');
          }
          context.pages.push({ title: cached.title, date: cached.date, tags: cached.tags, slug: cached.slug, html: cached.html });
          cache.pages[source] = cached;
          pagesSkipped += 1;
          timeSavedMs += cached.renderMs;
          continue;
        }
        const startedAt = Date.now();
        const file: PluginFile = { source, sourceContent, data: {}, title: '', tags: [], slug: '', html: '' };
        context.file = file;
        await this.run('onFile', context, file);
        if (file.output !== undefined) {
          const destination = join(resolvedOptions.outputDir, file.slug);
          await mkdir(dirname(destination), { recursive: true });
          await writeFile(destination, file.output, 'utf8');
        }
        context.pages.push({ title: file.title, date: file.date, tags: file.tags, slug: file.slug, html: file.html });
        cache.pages[source] = { title: file.title, date: file.date, tags: file.tags, slug: file.slug, html: file.html, sourceHash, output: file.output, data: file.data, renderMs: Date.now() - startedAt };
        pagesBuilt += 1;
      }
      context.file = undefined;
      context.pages.sort((left, right) => left.title.localeCompare(right.title));
      await this.run('afterBuild', context);
      if (canIncrement) {
        const currentSources = new Set(files);
        await Promise.all(Object.entries(previousCache!.pages).filter(([source]) => !currentSources.has(source)).map(async ([, page]) => {
          await unlink(join(resolvedOptions.outputDir, page.slug)).catch(() => undefined);
        }));
      }
      await writeFile(cachePath, JSON.stringify(cache, null, 2), 'utf8');
      this.lastBuildStats = { pagesBuilt, pagesSkipped, timeSavedMs };
      return context.pages;
    } finally {
      context.file = undefined;
      await this.run('onEnd', context);
    }
  }

  private async run(hook: keyof Plugin, context: PluginContext, file?: PluginFile): Promise<void> {
    for (const plugin of this.plugins) {
      const callback = plugin[hook];
      if (callback === undefined) continue;
      if (hook === 'onFile' && file !== undefined) await callback.call(plugin, file, context);
      else await (callback as (value: PluginContext) => void | Promise<void>).call(plugin, context);
    }
  }
}

export async function createEngine(plugins: Plugin[] = []): Promise<SsgEngine> {
  return new SsgEngine([new MarkdownPlugin(), ...plugins, ...await loadConfiguredPlugins(), new TemplatePlugin()]);
}
