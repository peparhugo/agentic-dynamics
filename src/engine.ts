import { promises as fs } from 'node:fs';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { loadPlugins } from './config';
import { MarkdownPlugin } from './plugins/markdown';
import { TemplatePlugin } from './plugins/template';
import type { BuildContext, BuildOptions, BuildStats, Page, Plugin } from './types';

interface CacheEntry {
  sourceHash: string;
  templateHash: string;
  pluginHash: string;
  outputPath: string;
  parsedPage: Page;
  page: Page;
  buildTimeMs: number;
}

interface CacheManifest {
  version: 1;
  pages: Record<string, CacheEntry>;
}

const hash = (value: string): string => createHash('sha256').update(value).digest('hex');

const pluginFingerprint = (plugin: Plugin): string => [
  plugin.name ?? '',
  plugin.onStart,
  plugin.beforeBuild,
  plugin.onFile,
  plugin.afterBuild,
  plugin.onEnd,
].map(String).join(':');

async function markdownFiles(directory: string, base = directory): Promise<string[]> {
  const entries = await fs.readdir(directory, { withFileTypes: true });
  const files = await Promise.all(entries.map(async (entry): Promise<string[]> => {
    const fullPath = path.join(directory, entry.name);
    if (entry.isDirectory()) return markdownFiles(fullPath, base);
    return entry.isFile() && /\.md$/i.test(entry.name) ? [path.relative(base, fullPath)] : [];
  }));
  return files.flat().sort((left, right) => left.localeCompare(right));
}

async function templateHashes(directory: string, base = directory): Promise<Map<string, string>> {
  const entries = await fs.readdir(directory, { withFileTypes: true }).catch((error: unknown) => {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return [];
    throw error;
  });
  const values = await Promise.all(entries.map(async (entry): Promise<Array<[string, string]>> => {
    const fullPath = path.join(directory, entry.name);
    if (entry.isDirectory()) return [...(await templateHashes(fullPath, base)).entries()];
    if (!entry.isFile() || !entry.name.toLowerCase().endsWith('.hbs')) return [];
    return [[path.relative(base, fullPath).split(path.sep).join('/'), hash(await fs.readFile(fullPath, 'utf8'))]];
  }));
  return new Map(values.flat().sort(([left], [right]) => left.localeCompare(right)));
}

const namedTemplate = (name: string): string => name.toLowerCase().endsWith('.hbs') ? name : `${name}.hbs`;

function pageTemplateHash(page: Page, templates: Map<string, string>): string {
  if (templates.size === 0) return hash('built-in-template-v1');
  const names = [
    namedTemplate(page.template ?? 'default'),
    `layouts/${namedTemplate(page.layout ?? 'default')}`,
    ...[...templates.keys()].filter((name) => name.startsWith('partials/')),
  ];
  return hash(names.sort().map((name) => `${name}:${templates.get(name) ?? 'missing'}`).join('\n'));
}

async function readManifest(filename: string): Promise<CacheManifest | undefined> {
  try {
    const parsed = JSON.parse(await fs.readFile(filename, 'utf8')) as CacheManifest;
    return parsed.version === 1 && parsed.pages && typeof parsed.pages === 'object' ? parsed : undefined;
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT' || error instanceof SyntaxError) return undefined;
    throw error;
  }
}

const isWithin = (relativePath: string): boolean => relativePath === '' || (!relativePath.startsWith('..') && !path.isAbsolute(relativePath));

export class SsgEngine {
  lastBuildStats?: BuildStats;

  constructor(private readonly options: BuildOptions = {}) {}

  async build(): Promise<Page[]> {
    const buildStarted = Date.now();
    const cacheFile = path.resolve(this.options.cacheFile ?? path.join(path.dirname(path.resolve(this.options.outputDir ?? './dist')), '.ssg-cache.json'));
    const previousManifest = this.options.incremental && !this.options.clean ? await readManifest(cacheFile) : undefined;
    const cleanBuild = !this.options.incremental || this.options.clean === true || !previousManifest;
    const context: BuildContext = {
      contentDir: path.resolve(this.options.contentDir ?? './content'),
      outputDir: path.resolve(this.options.outputDir ?? './dist'),
      templateDir: path.resolve(this.options.templateDir ?? './templates'),
      options: this.options,
      pages: [],
      incremental: { enabled: this.options.incremental === true, cleanBuild, skippedOutputPaths: new Set() },
      stats: { pagesBuilt: 0, pagesSkipped: 0, durationMs: 0, timeSavedMs: 0, cleanBuild },
    };
    this.validateDirectories(context);

    const stats = await fs.stat(context.contentDir).catch(() => undefined);
    if (!stats?.isDirectory()) throw new Error(`Content directory does not exist: ${context.contentDir}`);

    const markdown = new MarkdownPlugin();
    const configured = this.options.plugins ?? await loadPlugins(path.resolve(this.options.configFile ?? 'ssg.config.ts'));
    const plugins: Plugin[] = [markdown, ...configured, new TemplatePlugin()];
    let started = false;
    try {
      started = true;
      await this.runHook(plugins, 'onStart', context);
      await this.runHook(plugins, 'beforeBuild', context);
      const files = await markdownFiles(context.contentDir);
      const sources = new Map(await Promise.all(files.map(async (relativePath): Promise<[string, string]> => [
        relativePath,
        await fs.readFile(path.join(context.contentDir, relativePath), 'utf8'),
      ])));
      const sourceHashes = new Map([...sources].map(([name, source]) => [name, hash(source)]));
      const templates = await templateHashes(context.templateDir);
      const pluginHash = hash(plugins.map(pluginFingerprint).join('|'));
      const records = await Promise.all(files.map(async (relativePath) => {
        const cached = previousManifest?.pages[relativePath];
        const parsedPage = cached?.sourceHash === sourceHashes.get(relativePath) && cached.parsedPage
          ? cached.parsedPage
          : markdown.parse(sources.get(relativePath) as string, relativePath);
        return { relativePath, parsedPage, page: parsedPage };
      }));
      records.sort((left, right) => {
        if (left.page.date && right.page.date && left.page.date !== right.page.date) return right.page.date.localeCompare(left.page.date);
        if (left.page.date !== right.page.date) return left.page.date ? -1 : 1;
        return left.page.title.localeCompare(right.page.title);
      });
      context.pages = records.map((record) => record.page);
      const nextManifest: CacheManifest = { version: 1, pages: {} };
      for (let index = 0; index < context.pages.length; index += 1) {
        let page = context.pages[index];
        const { relativePath, parsedPage } = records[index];
        const cached = previousManifest?.pages[relativePath];
        const cachedDependencies = cached?.sourceHash === sourceHashes.get(relativePath) && cached.pluginHash === pluginHash
          ? cached.page
          : page;
        const templateHash = pageTemplateHash(cachedDependencies, templates);
        const destinationExists = await fs.stat(path.join(context.outputDir, cached?.outputPath ?? page.outputPath)).then((stats) => stats.isFile()).catch(() => false);
        if (!cleanBuild && cached?.sourceHash === sourceHashes.get(relativePath) && cached.templateHash === templateHash && cached.pluginHash === pluginHash && destinationExists) {
          page = cached.page;
          context.pages[index] = page;
          context.incremental.skippedOutputPaths.add(page.outputPath);
          context.stats.pagesSkipped += 1;
          context.stats.timeSavedMs += cached.buildTimeMs;
          nextManifest.pages[relativePath] = cached;
          continue;
        }
        const pageStarted = Date.now();
        for (const plugin of plugins) {
          page = await plugin.onFile?.(page, context) ?? page;
          context.pages[index] = page;
        }
        if (!cleanBuild && cached && cached.outputPath !== page.outputPath) {
          await fs.rm(path.join(context.outputDir, cached.outputPath), { force: true });
        }
        context.stats.pagesBuilt += 1;
        nextManifest.pages[relativePath] = {
          sourceHash: sourceHashes.get(relativePath) as string,
          templateHash: pageTemplateHash(page, templates),
          pluginHash,
          outputPath: page.outputPath,
          parsedPage,
          page,
          buildTimeMs: Math.max(1, Date.now() - pageStarted),
        };
      }
      if (!cleanBuild && previousManifest) {
        const stale = Object.entries(previousManifest.pages).filter(([source]) => !nextManifest.pages[source]);
        await Promise.all(stale.map(([, entry]) => fs.rm(path.join(context.outputDir, entry.outputPath), { force: true })));
      }
      await this.runHook(plugins, 'afterBuild', context);
      await fs.mkdir(path.dirname(cacheFile), { recursive: true });
      await fs.writeFile(cacheFile, `${JSON.stringify(nextManifest, null, 2)}\n`, 'utf8');
      context.stats.durationMs = Date.now() - buildStarted;
      this.lastBuildStats = context.stats;
      this.options.onStats?.(context.stats);
      return context.pages;
    } finally {
      if (started) await this.runHook(plugins, 'onEnd', context);
    }
  }

  private validateDirectories(context: BuildContext): void {
    if (isWithin(path.relative(context.contentDir, context.outputDir)) || isWithin(path.relative(context.outputDir, context.contentDir))) {
      throw new Error('Content and output directories must not overlap');
    }
  }

  private async runHook(plugins: Plugin[], hook: 'onStart' | 'beforeBuild' | 'afterBuild' | 'onEnd', context: BuildContext): Promise<void> {
    for (const plugin of plugins) await plugin[hook]?.(context);
  }
}
