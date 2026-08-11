import * as fs from 'fs';
import * as path from 'path';
import { Page } from './types';
import { Plugin, BuildContext } from './plugin';
import { loadConfig } from './config';
import { MarkdownPlugin } from '../plugins/markdown-plugin';
import { TemplatePlugin } from '../plugins/template-plugin';
import { BuildOptions } from './build';
import {
  SsgCacheManifest,
  CacheEntry,
  loadCache,
  saveCache,
  removeCache,
  createEmptyManifest,
  computeTemplatesHash,
  hashFile,
  BuildStats,
} from './cache';

function getDefaultPlugins(): Plugin[] {
  return [
    new MarkdownPlugin(),
    new TemplatePlugin(),
  ];
}

export class SsgEngine {
  private plugins: Plugin[];

  constructor(additionalPlugins?: Plugin[]) {
    const config = loadConfig();
    const configPlugins = config.plugins || [];
    if (configPlugins.length > 0) {
      this.plugins = [...configPlugins, ...(additionalPlugins || [])];
    } else {
      this.plugins = [...getDefaultPlugins(), ...(additionalPlugins || [])];
    }
  }

  build(contentDir: string, outputDir: string, templatesDir?: string, options?: BuildOptions): void {
    const absoluteContent = path.resolve(contentDir);
    const absoluteOutput = path.resolve(outputDir);

    if (!fs.existsSync(absoluteContent)) {
      throw new Error(`Content directory does not exist: ${absoluteContent}`);
    }

    const cachePath = path.join(absoluteOutput, '.ssg-cache.json');
    const incremental = options?.incremental === true;
    const clean = options?.clean === true;

    if (clean && fs.existsSync(cachePath)) {
      removeCache(cachePath);
    }

    let cache: SsgCacheManifest | null = null;
    if (incremental) {
      cache = loadCache(cachePath);
      if (!cache) {
        cache = createEmptyManifest();
      }
    }

    const templatesHash = templatesDir && fs.existsSync(templatesDir)
      ? computeTemplatesHash(path.resolve(templatesDir))
      : '';

    const skippedSlugs = new Set<string>();

    const ctx: BuildContext = {
      contentDir: absoluteContent,
      outputDir: absoluteOutput,
      templatesDir,
      cache,
      cachePath: incremental ? cachePath : undefined,
      skippedSlugs,
      templatesHash,
    };

    for (const plugin of this.plugins) {
      if (plugin.setContext) plugin.setContext(ctx);
    }

    for (const plugin of this.plugins) {
      if (plugin.onStart) plugin.onStart();
    }

    const files = fs.readdirSync(absoluteContent).filter((f) => f.endsWith('.md'));

    const pages: Page[] = [];
    const newCacheManifest: SsgCacheManifest = { version: 1, pages: {}, templatesHash };
    let pagesBuilt = 0;
    let pagesSkipped = 0;

    for (const file of files) {
      const slug = path.basename(file, '.md');
      const filePath = path.join(absoluteContent, file);
      const sourceHash = hashFile(filePath);

      const cachedEntry = cache?.pages[slug];
      const canSkip = incremental && cachedEntry &&
        cachedEntry.sourceHash === sourceHash &&
        cachedEntry.templatesHash === templatesHash;

      if (canSkip) {
        pagesSkipped++;
        skippedSlugs.add(slug);

        const outputPath = path.join(absoluteOutput, `${slug}.html`);
        if (!fs.existsSync(outputPath)) {
          if (!fs.existsSync(absoluteOutput)) {
            fs.mkdirSync(absoluteOutput, { recursive: true });
          }
          fs.writeFileSync(outputPath, cachedEntry.outputHtml);
        }

        newCacheManifest.pages[slug] = cachedEntry;

        const page: Page = {
          slug,
          title: cachedEntry.title || slug,
          date: cachedEntry.date,
          tags: cachedEntry.tags,
          template: cachedEntry.template,
          layout: cachedEntry.layout,
          content: '',
          html: cachedEntry.outputHtml,
        };
        pages.push(page);
      } else {
        pagesBuilt++;

        const content = fs.readFileSync(filePath, 'utf-8');
        const page: Page = {
          slug,
          title: slug,
          content,
          html: '',
        };
        pages.push(page);
      }
    }

    for (const plugin of this.plugins) {
      if (plugin.beforeBuild) plugin.beforeBuild();
    }

    for (const page of pages) {
      if (!skippedSlugs.has(page.slug)) {
        for (const plugin of this.plugins) {
          if (plugin.onFile) plugin.onFile(page);
        }
      }
    }

    pages.sort((a, b) => {
      if (a.date && b.date) {
        return b.date.localeCompare(a.date);
      }
      if (a.date) return -1;
      if (b.date) return 1;
      return a.title.localeCompare(b.title);
    });

    for (const plugin of this.plugins) {
      if (plugin.afterBuild) plugin.afterBuild(pages);
    }

    for (const plugin of this.plugins) {
      if (plugin.onEnd) plugin.onEnd();
    }

    for (const page of pages) {
      if (!skippedSlugs.has(page.slug)) {
        newCacheManifest.pages[page.slug] = {
          sourceHash: hashFile(path.join(absoluteContent, `${page.slug}.md`)),
          templatesHash,
          outputHtml: page.html || '',
          title: page.title,
          date: page.date,
          tags: page.tags,
          template: page.template,
          layout: page.layout,
        };
      }
    }

    if (incremental) {
      saveCache(cachePath, newCacheManifest);
      const stats: BuildStats = { pagesBuilt, pagesSkipped };
      console.log(`Build complete: ${stats.pagesBuilt} built, ${stats.pagesSkipped} skipped`);
    }
  }
}
