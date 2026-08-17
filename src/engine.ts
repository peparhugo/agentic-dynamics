import * as fs from 'fs';
import * as path from 'path';
import { Page, Plugin, BuildResult } from './plugin';
import { renderIndex } from './render';
import {
  CACHE_VERSION,
  CacheEntry,
  CacheManifest,
  defaultCacheFile,
  emptyManifest,
  hashTemplates,
  loadManifest,
  saveManifest,
  sha256,
} from './cache';

export interface EngineOptions {
  contentDir: string;
  outputDir: string;
  templatesDir?: string;
  incremental?: boolean;
  clean?: boolean;
  cacheFile?: string;
}

type LifecycleHook = 'onStart' | 'beforeBuild' | 'afterBuild' | 'onEnd';

function collectMarkdownFiles(dir: string): string[] {
  const results: string[] = [];
  if (!fs.existsSync(dir)) {
    return results;
  }
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      results.push(...collectMarkdownFiles(full));
    } else if (entry.isFile() && entry.name.toLowerCase().endsWith('.md')) {
      results.push(full);
    }
  }
  return results;
}

function toSlug(contentDir: string, filePath: string): string {
  const rel = path.relative(contentDir, filePath);
  const ext = path.extname(rel);
  const withoutExt = ext ? rel.slice(0, -ext.length) : rel;
  return withoutExt.split(path.sep).join('/');
}

export class Engine {
  private readonly options: EngineOptions;
  private readonly plugins: Plugin[];

  constructor(options: EngineOptions, plugins: Plugin[]) {
    this.options = options;
    this.plugins = plugins;
  }

  build(): BuildResult {
    const { contentDir, outputDir } = this.options;
    const templatesDir = this.options.templatesDir ?? path.resolve('templates');
    const incremental = this.options.incremental ?? false;
    const clean = this.options.clean ?? false;
    const cacheFile = this.options.cacheFile ?? defaultCacheFile(outputDir);

    this.emit('onStart');
    this.emit('beforeBuild');

    const startedAt = Date.now();

    if (clean) {
      try {
        fs.rmSync(cacheFile, { force: true });
      } catch {
        // ignore a missing or locked cache file
      }
    }

    const useCache = incremental;
    const manifest: CacheManifest = useCache
      ? loadManifest(cacheFile)
      : emptyManifest();
    const previous = manifest.pages ?? {};
    const templatesHash = useCache ? hashTemplates(templatesDir) : '';

    const files = collectMarkdownFiles(contentDir);

    fs.mkdirSync(outputDir, { recursive: true });

    const pages: Page[] = [];
    const nextPages: Record<string, CacheEntry> = {};

    let pagesBuilt = 0;
    let pagesSkipped = 0;
    let timeSavedMs = 0;

    for (const file of files) {
      const slug = toSlug(contentDir, file);
      const outputPath = `${slug}.html`;
      const outFile = path.join(outputDir, outputPath);

      let sourceHash = '';
      if (useCache) {
        sourceHash = sha256(fs.readFileSync(file, 'utf8'));
      }

      const prev = useCache ? previous[slug] : undefined;
      const canSkip =
        useCache &&
        prev !== undefined &&
        prev.sourceHash === sourceHash &&
        prev.templatesHash === templatesHash &&
        fs.existsSync(outFile);

      if (canSkip) {
        pages.push({
          slug,
          title: prev.title,
          date: prev.date,
          tags: prev.tags,
          html: prev.html,
          rendered: fs.readFileSync(outFile, 'utf8'),
          template: prev.template,
          layout: prev.layout,
          frontmatter: prev.frontmatter,
          sourcePath: file,
          outputPath,
        });
        nextPages[slug] = prev;
        pagesSkipped += 1;
        timeSavedMs += prev.buildTimeMs ?? 0;
        continue;
      }

      const pageStart = Date.now();
      const page = this.buildPage(slug, file, outputPath);
      const buildTimeMs = Date.now() - pageStart;

      fs.mkdirSync(path.dirname(outFile), { recursive: true });
      fs.writeFileSync(outFile, page.rendered);

      if (useCache) {
        nextPages[slug] = {
          slug,
          sourcePath: file,
          outputPath,
          sourceHash,
          templatesHash,
          title: page.title,
          date: page.date,
          tags: page.tags,
          template: page.template,
          layout: page.layout,
          frontmatter: page.frontmatter,
          html: page.html,
          buildTimeMs,
        };
      }

      pages.push(page);
      pagesBuilt += 1;
    }

    this.sortPages(pages);

    const indexPath = path.join(outputDir, 'index.html');
    fs.writeFileSync(indexPath, renderIndex(pages));

    if (incremental) {
      saveManifest(cacheFile, { version: CACHE_VERSION, pages: nextPages });
    }

    this.emit('afterBuild');
    this.emit('onEnd');

    const durationMs = Date.now() - startedAt;

    return {
      pages,
      outputDir,
      indexPath,
      stats: {
        pagesBuilt,
        pagesSkipped,
        timeSavedMs,
        durationMs,
        incremental,
      },
    };
  }

  private buildPage(slug: string, file: string, outputPath: string): Page {
    const page: Page = {
      slug,
      title: '',
      date: null,
      tags: [],
      html: '',
      rendered: '',
      template: null,
      layout: null,
      frontmatter: {},
      sourcePath: file,
      outputPath,
    };
    for (const plugin of this.plugins) {
      plugin.onFile?.(page);
    }
    return page;
  }

  private sortPages(pages: Page[]): void {
    pages.sort((a, b) => {
      const aDate = a.date;
      const bDate = b.date;
      if (!aDate && !bDate) {
        return a.title.localeCompare(b.title);
      }
      if (!aDate) {
        return 1;
      }
      if (!bDate) {
        return -1;
      }
      return bDate.localeCompare(aDate);
    });
  }

  private emit(hook: LifecycleHook): void {
    for (const plugin of this.plugins) {
      plugin[hook]?.();
    }
  }
}
