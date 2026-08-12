import type { BuildOptions, Page } from './generator';

export interface CacheEntry {
  sourceHash: string;
  templateHash: string;
  page: Page;
  output: string;
}

export interface BuildCache {
  entries: Record<string, CacheEntry>;
  templateHash: string;
}

export interface BuildStats {
  pagesBuilt: number;
  pagesSkipped: number;
  timeSaved: number;
}

export interface BuildContext {
  options: BuildOptions;
  contentDir: string;
  outputDir: string;
  templatesDir: string;
  pages: Page[];
  outputs: Map<string, string>;
  cache?: BuildCache;
  skippedOutputs?: Set<string>;
  stats?: BuildStats;
}

export interface Plugin {
  name?: string;
  onStart?(context: BuildContext): void | Promise<void>;
  beforeBuild?(context: BuildContext): void | Promise<void>;
  afterBuild?(context: BuildContext): void | Promise<void>;
  onFile?(page: Page, context: BuildContext): Page | void | Promise<Page | void>;
  onEnd?(context: BuildContext): void | Promise<void>;
}

export type PluginModule = Plugin | (() => Plugin);
