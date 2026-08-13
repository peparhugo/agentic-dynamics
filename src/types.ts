export interface BuildOptions {
  contentDir?: string;
  outputDir?: string;
  templatesDir?: string;
  configFile?: string;
  plugins?: Plugin[];
  incremental?: boolean;
  clean?: boolean;
  cacheFile?: string;
}

export interface BuildStats {
  pagesBuilt: number;
  pagesSkipped: number;
  timeSavedMs: number;
  durationMs: number;
}

export interface Page {
  title: string;
  date?: string;
  tags: string[];
  sourcePath: string;
  outputPath: string;
  url: string;
  html: string;
  data: Record<string, unknown>;
}

export interface BuildContext {
  readonly contentDir: string;
  readonly outputDir: string;
  readonly templatesDir: string;
  pages: Page[];
  readonly incremental: boolean;
  readonly pagesToBuild: Set<string>;
  readonly renderedHtml: Map<string, string>;
  stats: BuildStats;
  cache?: BuildCache;
}

export interface CachedPage {
  sourceHash: string;
  page: Page;
  renderedHtml: string;
  buildTimeMs: number;
}

export interface BuildCache {
  filename: string;
  templateHash: string;
  previousTemplateHash?: string;
  entries: Record<string, CachedPage>;
  previousEntries: Record<string, CachedPage>;
}

export interface BuildResult extends Array<Page> {
  readonly stats: BuildStats;
}

export type PluginHookResult = void | Promise<void>;

export interface Plugin {
  name?: string;
  onStart?(context: BuildContext): PluginHookResult;
  beforeBuild?(context: BuildContext): PluginHookResult;
  afterBuild?(context: BuildContext): PluginHookResult;
  onFile?(page: Page, context: BuildContext): PluginHookResult;
  onEnd?(context: BuildContext): PluginHookResult;
}

export interface SsgConfig {
  plugins?: Plugin[];
}
