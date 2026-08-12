import fs from 'fs/promises';
import path from 'path';
import { Plugin, PluginHook, SsgContext } from './plugin';
import { SsgConfig, loadConfiguredPlugins } from './config';
import { BuildOptions, Page } from './types';
import {
  collectMarkdownFiles,
  renderIndexHtml,
  slugFromSource,
} from './core';
import { parseFrontmatter } from './markdown';
import { computeHash } from './hash';
import {
  CacheManifest,
  CachedPage,
  BuildStats,
  loadCache,
  saveCache,
  CACHE_VERSION,
} from './cache';
import { computeTemplateHash, computePartialsFingerprint } from './template';
import { defaultPlugins } from './plugins';
import { DEFAULT_TEMPLATE_DIR } from './template';

function dedupePlugins(plugins: Plugin[]): Plugin[] {
  const seen = new Set<string>();
  const result: Plugin[] = [];
  for (const plugin of plugins) {
    if (!plugin || seen.has(plugin.name)) continue;
    seen.add(plugin.name);
    result.push(plugin);
  }
  return result;
}

export class SsgEngine {
  readonly context: SsgContext;
  readonly plugins: Plugin[];
  lastBuildStats: BuildStats = {
    built: 0,
    skipped: 0,
    total: 0,
    timeSavedMs: 0,
    totalMs: 0,
  };

  constructor(
    readonly options: BuildOptions,
    extraPlugins: Plugin[] = [],
    readonly config: SsgConfig = {}
  ) {
    this.plugins = dedupePlugins([...defaultPlugins(), ...extraPlugins]);
    this.context = {
      options,
      config: this.config,
      engine: this,
      pages: [],
      templateDir: path.resolve(options.templateDir ?? DEFAULT_TEMPLATE_DIR),
      startTime: Date.now(),
    };
  }

  async start(): Promise<void> {
    await this.runHook('onStart');
  }

  async build(): Promise<Page[]> {
    await this.runHook('beforeBuild');
    const buildStart = Date.now();

    const cache =
      this.options.incremental && !this.options.clean
        ? await loadCache(this.options.outputDir)
        : undefined;

    const { pages, manifest, built, skipped, timeSavedMs } =
      await this.buildPages(cache);

    this.context.pages = pages;
    await this.writeOutput(pages);
    await saveCache(this.options.outputDir, manifest);

    this.lastBuildStats = {
      built,
      skipped,
      total: pages.length,
      timeSavedMs,
      totalMs: Date.now() - buildStart,
    };
    await this.runHook('afterBuild');
    return pages;
  }

  async close(): Promise<void> {
    await this.runHook('onEnd');
  }

  private async runHook(hook: PluginHook, arg?: unknown): Promise<void> {
    for (const plugin of this.plugins) {
      const fn = (plugin as unknown as Record<string, unknown>)[hook];
      if (typeof fn === 'function') {
        await (fn as (a: unknown) => unknown).call(plugin, arg ?? this.context);
      }
    }
  }

  private async buildPages(cache?: CacheManifest): Promise<{
    pages: Page[];
    manifest: CacheManifest;
    built: number;
    skipped: number;
    timeSavedMs: number;
  }> {
    const sources = await collectMarkdownFiles(this.options.contentDir);
    const pages: Page[] = [];
    const manifestPages: Record<string, CachedPage> = {};
    const templateDir = this.context.templateDir;

    let built = 0;
    let skipped = 0;
    let timeSavedMs = 0;

    const partialsFingerprint = await computePartialsFingerprint(templateDir);

    for (const source of sources) {
      const absPath = path.join(this.options.contentDir, source);
      const raw = await fs.readFile(absPath, 'utf-8');
      const hash = computeHash(raw);
      const frontmatter = parseFrontmatter(raw);
      const templateHash = await computeTemplateHash(
        templateDir,
        { template: frontmatter.template, layout: frontmatter.layout },
        partialsFingerprint
      );

      const cached = cache?.pages[source];
      if (
        cached &&
        cached.hash === hash &&
        cached.templateHash === templateHash
      ) {
        pages.push({ ...cached.page });
        manifestPages[source] = cached;
        skipped++;
        timeSavedMs += cached.buildMs;
        continue;
      }

      const pageStart = Date.now();
      let page: Page = {
        slug: slugFromSource(source),
        source,
        title: '',
        date: undefined,
        tags: [],
        body: '',
        html: '',
      };
      for (const plugin of this.plugins) {
        if (typeof plugin.onFile === 'function') {
          const result = await plugin.onFile(page, this.context);
          if (result) page = result;
        }
      }
      const buildMs = Date.now() - pageStart;
      pages.push(page);
      built++;
      manifestPages[source] = {
        hash,
        templateHash,
        buildMs,
        page,
      };
    }

    const manifest: CacheManifest = {
      version: CACHE_VERSION,
      generatedAt: new Date().toISOString(),
      pages: manifestPages,
    };

    return { pages, manifest, built, skipped, timeSavedMs };
  }

  private async writeOutput(pages: Page[]): Promise<void> {
    const outputDir = this.options.outputDir;
    await fs.rm(outputDir, { recursive: true, force: true });
    await fs.mkdir(outputDir, { recursive: true });
    for (const page of pages) {
      const dest = path.join(outputDir, `${page.slug}.html`);
      await fs.mkdir(path.dirname(dest), { recursive: true });
      await fs.writeFile(dest, page.renderedHtml ?? page.html, 'utf-8');
    }
    await fs.writeFile(
      path.join(outputDir, 'index.html'),
      renderIndexHtml(pages),
      'utf-8'
    );
  }
}

export function createEngine(
  options: BuildOptions,
  plugins?: Plugin[],
  config?: SsgConfig
): SsgEngine {
  return new SsgEngine(options, plugins ?? [], config ?? {});
}

export async function buildSite(
  options: BuildOptions,
  onStats?: (stats: BuildStats) => void
): Promise<Page[]> {
  const { plugins, config } = await loadConfiguredPlugins();
  const engine = createEngine(options, plugins, config);
  await engine.start();
  try {
    const pages = await engine.build();
    if (onStats) onStats(engine.lastBuildStats);
    return pages;
  } finally {
    await engine.close();
  }
}
