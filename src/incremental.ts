import * as fs from 'fs';
import * as path from 'path';
import { CacheManifest, cachePathFor, emptyManifest, hashContent, hashTemplatesDir, saveManifest, tryLoadManifest } from './cache';
import { findMarkdownFiles } from './markdownLoader';
import { parseMarkdown } from './parser';
import { DEFAULT_STYLESHEET, writeFile } from './plugins/templatePlugin';
import { TemplateEngine } from './templateEngine';
import { renderIndex, renderPage } from './templates';
import { BuildOptions, BuildResult, Page } from './types';

/** Fallback estimate (ms) for a page's build cost when no page was built
 * this run and the cache has no prior average to draw on. */
const DEFAULT_PAGE_BUILD_MS = 5;

export interface IncrementalBuildOptions {
  /** Ignore any existing cache and rebuild every page from scratch. */
  clean?: boolean;
}

export interface BuildStats {
  pagesBuilt: number;
  pagesSkipped: number;
  totalPages: number;
  /** Wall-clock time this build call took, in milliseconds. */
  elapsedMs: number;
  /** Estimated time saved by skipping unchanged pages, in milliseconds. */
  timeSavedMs: number;
  /** Whether this run was a clean (non-incremental) build. */
  clean: boolean;
}

export interface IncrementalBuildResult extends BuildResult {
  stats: BuildStats;
}

/**
 * Builds the site using the built-in Markdown + Template pipeline, skipping
 * work for pages whose source file and applicable templates are unchanged
 * since the last build. Progress is tracked in a `.ssg-cache.json` manifest
 * inside `outputDir`; the on-disk HTML output doubles as the rendered-HTML
 * cache (an unchanged page's existing output file is left in place rather
 * than re-rendered and re-written), while parsed frontmatter and page
 * metadata are cached directly in the manifest.
 *
 * Falls back to a full ("clean") build when the cache is missing, corrupt,
 * or `options.clean` is set. Does not affect `buildSite()`, which remains
 * a plain, non-caching build.
 */
export function buildSiteIncremental(
  options: BuildOptions,
  incrementalOptions: IncrementalBuildOptions = {}
): IncrementalBuildResult {
  const start = Date.now();
  const { contentDir, outputDir, templatesDir } = options;

  if (!fs.existsSync(contentDir)) {
    throw new Error(`Content directory not found: ${contentDir}`);
  }

  fs.mkdirSync(outputDir, { recursive: true });
  const cachePath = cachePathFor(outputDir);
  const { manifest: loadedManifest, valid: hadUsableCache } = tryLoadManifest(cachePath);
  const clean = !!incrementalOptions.clean || !hadUsableCache;
  const previousManifest = clean ? emptyManifest() : loadedManifest;

  const engine = templatesDir && fs.existsSync(templatesDir) ? new TemplateEngine(templatesDir) : undefined;
  const templatesHash = hashTemplatesDir(templatesDir);

  const sourceFiles = findMarkdownFiles(contentDir).sort();
  const sourceFileSet = new Set(sourceFiles);

  // First pass: figure out which pages can reuse their cache entry. This
  // only needs a raw read + hash (cheap) — no markdown parsing or
  // rendering — so the expensive work is skipped, not just its output.
  const reused = new Map<string, Page>();
  const toBuild: Array<{ relativePath: string; raw: string; sourceHash: string }> = [];

  for (const relativePath of sourceFiles) {
    const raw = fs.readFileSync(path.join(contentDir, relativePath), 'utf-8');
    const sourceHash = hashContent(raw);
    const cached = previousManifest.entries[relativePath];
    const outputPath = cached ? path.join(outputDir, cached.page.outputFile) : undefined;

    const canReuse =
      !clean &&
      !!cached &&
      cached.sourceHash === sourceHash &&
      cached.templatesHash === templatesHash &&
      !!outputPath &&
      fs.existsSync(outputPath);

    if (canReuse && cached) {
      reused.set(relativePath, cached.page);
    } else {
      toBuild.push({ relativePath, raw, sourceHash });
    }
  }

  // Pages that were rebuilt need the *full* page list (reused + rebuilt)
  // for cross-page rendering (e.g. "related posts" in a layout), so parse
  // every to-be-built page's frontmatter before rendering any of them.
  const freshPages = new Map<string, Page>();
  for (const { relativePath, raw } of toBuild) {
    freshPages.set(relativePath, parseMarkdown(raw, relativePath));
  }

  const pages: Page[] = sourceFiles.map((relativePath) => reused.get(relativePath) ?? freshPages.get(relativePath)!);

  const nextEntries: CacheManifest['entries'] = {};
  let builtTimeMs = 0;

  for (const relativePath of sourceFiles) {
    const cached = previousManifest.entries[relativePath];
    if (reused.has(relativePath) && cached) {
      nextEntries[relativePath] = cached;
      continue;
    }

    const pageStart = Date.now();
    const page = freshPages.get(relativePath)!;
    const html = engine?.renderPage(page, pages) ?? renderPage(page);
    writeFile(path.join(outputDir, page.outputFile), html);
    builtTimeMs += Date.now() - pageStart;

    const raw = toBuild.find((entry) => entry.relativePath === relativePath)!;
    nextEntries[relativePath] = { sourceHash: raw.sourceHash, templatesHash, page };
  }

  // Remove output + cache entries for source files that no longer exist.
  for (const relativePath of Object.keys(previousManifest.entries)) {
    if (sourceFileSet.has(relativePath)) continue;
    const stalePage = previousManifest.entries[relativePath].page;
    const staleOutputPath = path.join(outputDir, stalePage.outputFile);
    if (fs.existsSync(staleOutputPath)) {
      fs.rmSync(staleOutputPath);
    }
  }

  const indexHtml = engine?.renderIndex(pages) ?? renderIndex(pages);
  writeFile(path.join(outputDir, 'index.html'), indexHtml);
  writeFile(path.join(outputDir, 'style.css'), DEFAULT_STYLESHEET);

  const pagesBuilt = toBuild.length;
  const pagesSkipped = reused.size;
  const avgBuildMs = pagesBuilt > 0 ? builtTimeMs / pagesBuilt : previousManifest.meta.avgBuildMs ?? DEFAULT_PAGE_BUILD_MS;

  saveManifest(cachePath, {
    version: 1,
    entries: nextEntries,
    meta: { avgBuildMs },
  });

  const elapsedMs = Date.now() - start;
  const timeSavedMs = Math.round(avgBuildMs * pagesSkipped);

  return {
    pages,
    outputDir,
    stats: {
      pagesBuilt,
      pagesSkipped,
      totalPages: pages.length,
      elapsedMs,
      timeSavedMs,
      clean,
    },
  };
}
