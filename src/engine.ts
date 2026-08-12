import { mkdir, readFile, rm, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { DEFAULT_TEMPLATE_DIR } from './templates';
import { collectMarkdownFiles, comparePages, renderIndex, toSlug } from './render';
import { PluginManager, type Plugin, type PluginContext, type PluginFile } from './plugin';
import { MarkdownPlugin } from './plugins/markdown';
import { TemplatePlugin } from './plugins/templates';
import { loadConfig } from './config';
import {
  CACHE_FILE,
  CACHE_VERSION,
  computeTemplateHash,
  hashString,
  loadManifest,
  saveManifest,
  type CachedPage,
} from './cache';
import type { BuildResult, BuildStats, Page } from './types';

export interface SSGEngineOptions {
  plugins?: Plugin[];
  templatesDir?: string;
  port?: number;
  configPath?: string;
  incremental?: boolean;
  clean?: boolean;
  cacheFile?: string;
}

export class SSGEngine {
  private readonly manager: PluginManager;
  private readonly options: SSGEngineOptions;

  constructor(options: SSGEngineOptions = {}) {
    this.options = options;
    const config = loadConfig(options.configPath ?? 'ssg.config.ts');
    const configured = [...(config?.plugins ?? []), ...(options.plugins ?? [])];

    const plugins: Plugin[] = [];
    if (!configured.some((plugin) => plugin.name === 'markdown')) {
      plugins.push(new MarkdownPlugin());
    }
    if (!configured.some((plugin) => plugin.name === 'templates')) {
      plugins.push(new TemplatePlugin(options.templatesDir));
    }
    plugins.push(...configured);

    this.manager = new PluginManager(plugins);
  }

  getPlugins(): Plugin[] {
    return this.manager.getPlugins();
  }

  addPlugin(plugin: Plugin): void {
    this.manager.register(plugin);
  }

  async build(contentDir: string, outputDir: string): Promise<BuildResult> {
    const templatesDir = this.options.templatesDir ?? DEFAULT_TEMPLATE_DIR;
    const incremental = this.options.incremental === true;
    const clean = this.options.clean === true;
    const cacheFile = this.options.cacheFile ?? path.join(outputDir, CACHE_FILE);
    const startedAt = Date.now();

    if (clean) {
      await rm(cacheFile, { force: true });
    }

    const templateHash = await computeTemplateHash(templatesDir);
    const pluginNames = this.manager
      .getPlugins()
      .map((plugin) => plugin.name)
      .sort();

    let manifest: import('./cache').CacheManifest | null = null;
    if (incremental) {
      manifest = await loadManifest(cacheFile);
      if (
        manifest &&
        (manifest.templateHash !== templateHash || manifest.plugins.join('\n') !== pluginNames.join('\n'))
      ) {
        manifest = null;
      }
    }

    const context: PluginContext = {
      contentDir,
      outputDir,
      templatesDir,
      port: this.options.port ?? 3000,
      pages: [],
      files: [],
      options: { ...this.options },
    };

    await this.manager.runHook('onStart', context);
    await this.manager.runHook('beforeBuild', context);

    const works = await this.collectPages(contentDir);
    const pages: PluginFile[] = [];
    const nextEntries: Record<string, CachedPage> = {};
    let built = 0;
    let skipped = 0;
    let timeSaved = 0;

    for (const work of works) {
      const key = work.source;
      const sourceHash = hashString(work.raw);
      const cached = manifest?.entries[key];

      if (cached && cached.sourceHash === sourceHash) {
        pages.push({
          ...work,
          title: cached.title,
          date: cached.date,
          tags: cached.tags,
          html: cached.html,
          template: cached.template,
          layout: cached.layout,
          data: cached.data,
        });
        nextEntries[key] = { ...cached, sourceHash };
        skipped += 1;
        timeSaved += cached.renderTimeMs;
      } else {
        const renderStart = process.hrtime.bigint();
        const page = await this.manager.runOnFile(work, context);
        nextEntries[key] = {
          source: work.source,
          slug: page.slug,
          sourceHash,
          html: page.html,
          title: page.title,
          date: page.date,
          tags: page.tags,
          template: page.template,
          layout: page.layout,
          data: page.data,
          renderTimeMs: Number(process.hrtime.bigint() - renderStart) / 1e6,
        };
        pages.push(page);
        built += 1;
      }
    }
    pages.sort(comparePages);
    context.pages = pages;

    await mkdir(outputDir, { recursive: true });
    const files: string[] = [];
    for (const page of pages) {
      const outPath = path.join(outputDir, `${page.slug}.html`);
      await mkdir(path.dirname(outPath), { recursive: true });
      await writeFile(outPath, page.html, 'utf8');
      files.push(outPath);
    }
    const indexPath = path.join(outputDir, 'index.html');
    await writeFile(indexPath, renderIndex(pages), 'utf8');
    files.push(indexPath);
    context.files = files;

    await saveManifest(cacheFile, {
      version: CACHE_VERSION,
      templateHash,
      plugins: pluginNames,
      entries: nextEntries,
    });

    await this.manager.runHook('afterBuild', context);
    await this.manager.runHook('onEnd', context);

    const stats: BuildStats = {
      total: pages.length,
      built,
      skipped,
      timeSaved,
      time: Date.now() - startedAt,
      incremental,
    };

    return { pages, files, stats };
  }

  private async collectPages(contentDir: string): Promise<PluginFile[]> {
    const files = await collectMarkdownFiles(contentDir);
    const works: PluginFile[] = [];
    for (const file of files) {
      const raw = await readFile(file, 'utf8');
      const relative = path.relative(contentDir, file);
      works.push({
        title: '',
        date: '',
        tags: [],
        slug: toSlug(relative),
        source: relative,
        html: '',
        raw,
        contentDir,
      });
    }
    return works;
  }
}

export type { Page };
