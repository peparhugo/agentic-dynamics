import { promises as fs } from 'node:fs';
import { createHash } from 'node:crypto';
import path from 'node:path';
import { resolveConfig } from './config';
import { MarkdownPlugin } from './plugins/markdown';
import { indexDocument, TemplatePlugin } from './plugins/template';
import type { BuildOptions, BuildStats, Page, Plugin, PluginContext, PluginPage, ResolvedBuildOptions } from './plugin';

const cacheFileName = '.ssg-cache.json';
const cacheVersion = 1;

interface CacheEntry {
  sourceHash: string;
  templateHash: string;
  buildTimeMs: number;
  page: PluginPage;
}

interface CacheManifest {
  version: number;
  pages: Record<string, CacheEntry>;
}

function hash(value: string): string {
  return createHash('sha256').update(value).digest('hex');
}

async function exists(file: string): Promise<boolean> {
  try {
    await fs.access(file);
    return true;
  } catch {
    return false;
  }
}

async function readManifest(file: string): Promise<CacheManifest | undefined> {
  try {
    const manifest = JSON.parse(await fs.readFile(file, 'utf8')) as CacheManifest;
    return manifest.version === cacheVersion && manifest.pages && typeof manifest.pages === 'object'
      ? manifest
      : undefined;
  } catch {
    return undefined;
  }
}

async function templateHash(directory: string): Promise<string> {
  if (!await exists(directory)) return hash('');
  const files = await filesWithExtension(directory, /\.hbs$/i);
  const contents = await Promise.all(files.map(async (file) =>
    `${path.relative(directory, file)}\0${await fs.readFile(file, 'utf8')}`));
  return hash(contents.join('\0'));
}

async function filesWithExtension(directory: string, extension: RegExp): Promise<string[]> {
  const entries = await fs.readdir(directory, { withFileTypes: true });
  const files = await Promise.all(entries.map(async (entry) => {
    const entryPath = path.join(directory, entry.name);
    if (entry.isDirectory()) return filesWithExtension(entryPath, extension);
    return extension.test(entry.name) ? [entryPath] : [];
  }));
  return files.flat().sort();
}

async function markdownFiles(directory: string): Promise<string[]> {
  return filesWithExtension(directory, /\.md$/i);
}

function cachedPage(page: PluginPage): PluginPage {
  return { ...page, tags: [...page.tags], data: { ...page.data } };
}

function cacheKey(contentDir: string, file: string): string {
  return path.relative(contentDir, file).split(path.sep).join('/');
}

function publicPage(page: PluginPage): Page {
  return { title: page.title, date: page.date, tags: page.tags, outputPath: page.outputPath };
}

export interface BuildEngine {
  readonly context: PluginContext;
  readonly plugins: Plugin[];
  readonly stats: BuildStats;
  start(): Promise<void>;
  build(): Promise<Page[]>;
  end(): Promise<void>;
}

export async function createBuildEngine(options: BuildOptions = {}, additionalPlugins: Plugin[] = []): Promise<BuildEngine> {
  const { config, baseDir } = await resolveConfig(options);
  const resolveDirectory = (value: string | undefined, fallback: string): string =>
    path.resolve(baseDir, value ?? fallback);
  const resolved: ResolvedBuildOptions = {
    contentDir: resolveDirectory(options.contentDir ?? config.contentDir, './content'),
    outputDir: resolveDirectory(options.outputDir ?? config.outputDir, './dist'),
    templatesDir: resolveDirectory(options.templatesDir ?? config.templatesDir, './templates'),
    incremental: options.incremental ?? config.incremental ?? false,
    clean: options.clean ?? config.clean ?? false
  };
  const plugins: Plugin[] = [
    new MarkdownPlugin(),
    new TemplatePlugin(),
    ...(config.plugins ?? []),
    ...(options.plugins ?? []),
    ...additionalPlugins
  ];
  let started = false;
  let ended = false;
  let building = false;
  const stats: BuildStats = { pagesBuilt: 0, pagesSkipped: 0, durationMs: 0, timeSavedMs: 0 };

  const context: PluginContext = {
    options: resolved,
    pages: [],
    stats,
    build: async () => engine.build()
  };
  const run = async (hook: keyof Plugin): Promise<void> => {
    for (const plugin of plugins) {
      const callback = plugin[hook];
      if (typeof callback === 'function') {
        await (callback as (context: PluginContext) => void | Promise<void>).call(plugin, context);
      }
    }
  };
  const engine: BuildEngine = {
    context,
    plugins,
    stats,
    async start(): Promise<void> {
      if (started) return;
      started = true;
      await run('onStart');
    },
    async build(): Promise<Page[]> {
      if (building) throw new Error('A build is already in progress');
      building = true;
      const buildStarted = performance.now();
      try {
        await engine.start();
        context.pages = [];
        await run('beforeBuild');
        const manifestPath = path.join(resolved.outputDir, cacheFileName);
        const previous = resolved.incremental && !resolved.clean ? await readManifest(manifestPath) : undefined;
        if (resolved.clean || (resolved.incremental && !previous)) {
          await fs.rm(resolved.outputDir, { recursive: true, force: true });
        }
        await fs.mkdir(resolved.outputDir, { recursive: true });
        const currentTemplateHash = await templateHash(resolved.templatesDir);
        const next: CacheManifest = { version: cacheVersion, pages: {} };
        stats.pagesBuilt = 0;
        stats.pagesSkipped = 0;
        stats.timeSavedMs = 0;
        const sourceFiles = await markdownFiles(resolved.contentDir);
        for (const file of sourceFiles) {
          const sourceKey = cacheKey(resolved.contentDir, file);
          const relativePath = path.relative(resolved.contentDir, file).replace(/\.md$/i, '.html');
          const source = await fs.readFile(file, 'utf8');
          const sourceHash = hash(source);
          const prior = previous?.pages[sourceKey];
          const destination = path.join(resolved.outputDir, prior?.page.outputPath ?? relativePath);
          if (prior && prior.sourceHash === sourceHash && prior.templateHash === currentTemplateHash
            && await exists(destination)) {
            const page = cachedPage(prior.page);
            context.pages.push(page);
            next.pages[sourceKey] = { ...prior, page };
            stats.pagesSkipped += 1;
            stats.timeSavedMs += prior.buildTimeMs;
            continue;
          }
          const pageStarted = performance.now();
          const page: PluginPage = {
            title: path.basename(file, path.extname(file)),
            tags: [],
            outputPath: relativePath,
            sourcePath: file,
            source,
            data: {},
            content: '',
            html: ''
          };
          for (const plugin of plugins) await plugin.onFile?.(page, context);
          const pageDestination = path.join(resolved.outputDir, page.outputPath);
          await fs.mkdir(path.dirname(pageDestination), { recursive: true });
          await fs.writeFile(pageDestination, page.html, 'utf8');
          context.pages.push(page);
          stats.pagesBuilt += 1;
          next.pages[sourceKey] = {
            sourceHash,
            templateHash: currentTemplateHash,
            buildTimeMs: performance.now() - pageStarted,
            page: cachedPage(page)
          };
        }
        if (previous) {
          for (const [source, entry] of Object.entries(previous.pages)) {
            if (!next.pages[source]) {
              await fs.rm(path.join(resolved.outputDir, entry.page.outputPath), { force: true });
            }
          }
        }
        context.pages.sort((left, right) => {
          if (left.date && right.date && left.date !== right.date) return right.date.localeCompare(left.date);
          if (left.date !== right.date) return left.date ? -1 : 1;
          return left.title.localeCompare(right.title);
        });
        await fs.writeFile(path.join(resolved.outputDir, 'index.html'), indexDocument(context.pages), 'utf8');
        if (resolved.incremental) await fs.writeFile(manifestPath, JSON.stringify(next, null, 2), 'utf8');
        stats.durationMs = performance.now() - buildStarted;
        await run('afterBuild');
        return context.pages.map(publicPage);
      } finally {
        building = false;
      }
    },
    async end(): Promise<void> {
      if (!started || ended) return;
      ended = true;
      await run('onEnd');
    }
  };
  return engine;
}

export async function buildSite(options: BuildOptions = {}): Promise<Page[]> {
  const engine = await createBuildEngine(options);
  try {
    return await engine.build();
  } finally {
    await engine.end();
  }
}
