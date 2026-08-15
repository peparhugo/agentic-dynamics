import type { Page } from './generator';

export interface CachePageEntry {
  sourceHash: string;
  templateHash: string;
  page: Page;
  parsedPage?: Page;
  buildTimeMs: number;
}

export interface BuildCache {
  version: 1;
  templateHash: string;
  pages: Record<string, CachePageEntry>;
}

export interface BuildState {
  incremental: boolean;
  clean: boolean;
  cache: BuildCache;
  cachePath: string;
  builtSources: Set<string>;
  skippedSources: Set<string>;
  sourceHashes: Map<string, string>;
  templateHash: string;
  timeSavedMs: number;
  pageTimes: Map<string, number>;
  parsedPages: Map<string, Page>;
}

export interface BuildContext {
  contentDir: string;
  outputDir: string;
  templatesDir: string;
  pages: Page[];
  files: string[];
  data: Map<string, unknown>;
  build?: BuildState;
}

export interface Plugin {
  name?: string;
  onStart?(context: BuildContext): void | Promise<void>;
  beforeBuild?(context: BuildContext): void | Promise<void>;
  afterBuild?(context: BuildContext): void | Promise<void>;
  onFile?(page: Page, context: BuildContext): Page | void | Promise<Page | void>;
  onEnd?(context: BuildContext): void | Promise<void>;
}

export type PluginFactory = Plugin | (() => Plugin | Promise<Plugin>);
