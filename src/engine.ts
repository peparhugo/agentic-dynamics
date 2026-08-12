import fs from 'fs';
import path from 'path';
import { Page, BuildOptions, BuildStats, IncrementalBuildOptions } from './types';
import { Plugin, PluginContext, PluginPipeline } from './plugin';
import { collectMarkdownFiles } from './collect';
import { slugify } from './parse';
import {
  CacheManifest,
  CACHE_VERSION,
  computeTemplateHash,
  hashFile,
  loadManifest,
  saveManifest,
} from './cache';

export interface SSGOptions {
  options: BuildOptions;
  plugins: Plugin[];
}

export class SSG {
  readonly options: BuildOptions;
  private pipeline: PluginPipeline;
  private ctx: PluginContext;
  private started = false;
  lastBuildStats: BuildStats | undefined;

  constructor(opts: SSGOptions) {
    this.options = opts.options;
    this.pipeline = new PluginPipeline(opts.plugins);
    this.ctx = {
      engine: this,
      options: this.options,
      pages: [],
      writeFile: (relPath, content) => {
        const out = path.join(this.options.outputDir, relPath);
        fs.mkdirSync(path.dirname(out), { recursive: true });
        fs.writeFileSync(out, content, 'utf-8');
      },
    };
  }

  get plugins(): Plugin[] {
    return this.pipeline.plugins;
  }

  start(): this {
    if (this.started) return this;
    this.started = true;
    this.pipeline.run('onStart', this.ctx);
    return this;
  }

  build(buildOptions?: IncrementalBuildOptions): Page[] {
    const wantIncremental =
      !!(buildOptions && buildOptions.incremental) && !(buildOptions && buildOptions.clean);
    const manifest = wantIncremental ? loadManifest(this.options.outputDir) : undefined;
    const incremental = wantIncremental && !!manifest;
    const startTime = Date.now();

    const templateHash = computeTemplateHash(
      this.options.contentDir,
      this.options.templatesDir
    );
    const templateChanged = !manifest || manifest.templateHash !== templateHash;

    if (incremental) {
      fs.mkdirSync(this.options.outputDir, { recursive: true });
    } else {
      fs.rmSync(this.options.outputDir, { recursive: true, force: true });
      fs.mkdirSync(this.options.outputDir, { recursive: true });
    }

    this.ctx.pages = [];
    this.pipeline.run('beforeBuild', this.ctx);

    const previousPages = manifest ? manifest.pages : {};
    const newManifest: CacheManifest = {
      version: CACHE_VERSION,
      templateHash,
      pages: {},
    };

    let built = 0;
    let skipped = 0;
    let timeSavedMs = 0;

    for (const file of collectMarkdownFiles(this.options.contentDir)) {
      const slug = slugify(file);
      this.ctx.currentFile = file;
      const sourceHash = hashFile(file);
      const cached = previousPages[slug];

      if (
        !templateChanged &&
        cached &&
        cached.sourceHash === sourceHash &&
        cached.templateHash === templateHash
      ) {
        this.ctx.pages.push(cached.page);
        newManifest.pages[slug] = cached;
        timeSavedMs += cached.renderMs;
        skipped += 1;
        const out = path.join(this.options.outputDir, `${slug}.html`);
        if (!fs.existsSync(out)) {
          fs.mkdirSync(path.dirname(out), { recursive: true });
          fs.writeFileSync(out, cached.page.html, 'utf-8');
        }
        continue;
      }

      const raw = fs.readFileSync(file, 'utf-8');
      const page: Page = { slug, content: raw, html: '', data: {} };
      const pageStart = Date.now();
      const result = this.pipeline.runFile(page, this.ctx);
      newManifest.pages[slug] = {
        sourceHash,
        templateHash,
        renderMs: Date.now() - pageStart,
        page: result,
      };
      this.ctx.pages.push(result);
      this.ctx.writeFile(`${result.slug}.html`, result.html);
      built += 1;
    }

    for (const slug of Object.keys(previousPages)) {
      if (!newManifest.pages[slug]) {
        const out = path.join(this.options.outputDir, `${slug}.html`);
        if (fs.existsSync(out)) fs.rmSync(out, { force: true });
      }
    }

    this.pipeline.run('afterBuild', this.ctx);
    saveManifest(this.options.outputDir, newManifest);
    this.pipeline.run('onEnd', this.ctx);

    this.lastBuildStats = {
      total: this.ctx.pages.length,
      built,
      skipped,
      timeMs: Date.now() - startTime,
      timeSavedMs,
      usedCache: incremental && !templateChanged,
    };
    return this.ctx.pages;
  }
}

export function createSSG(options: SSGOptions): SSG {
  return new SSG(options);
}
