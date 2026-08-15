import type { Plugin } from './plugin';

export interface Frontmatter {
  title?: string;
  date?: string;
  tags?: string[];
  template?: string;
  layout?: string;
}

export interface Page {
  slug: string;
  title: string;
  date?: string;
  tags: string[];
  html: string;
  sourcePath: string;
  template?: string;
  layout?: string;
  data: Record<string, unknown>;
  /** SHA-256 hash of the source file, populated during incremental builds. */
  sourceHash?: string;
  /** True when this page was restored from the cache instead of re-rendered. */
  fresh?: boolean;
}

export interface BuildStats {
  pagesBuilt: number;
  pagesSkipped: number;
  timeSavedMs: number;
}

export interface BuildOptions {
  contentDir: string;
  outputDir: string;
  templatesDir?: string;
  plugins?: Plugin[];
  config?: string;
  /** Only rebuild pages whose source or template changed. */
  incremental?: boolean;
  /** Force a full rebuild and discard the cache. */
  clean?: boolean;
  /** Override the location of the `.ssg-cache.json` manifest. */
  cacheFile?: string;
}

export interface BuildResult {
  pages: Page[];
  outputDir: string;
  stats: BuildStats;
}

export interface ServeOptions {
  contentDir: string;
  outputDir: string;
  templatesDir?: string;
  port?: number;
  host?: string;
}
