export interface Frontmatter {
  title?: string;
  date?: string | Date;
  tags?: string[] | string;
  template?: string;
  layout?: string;
  [key: string]: unknown;
}

export interface Page {
  title: string;
  date?: string;
  tags: string[];
  html: string;
  outputPath: string;
  url: string;
  template?: string;
  layout?: string;
  data?: Frontmatter;
}

export interface BuildOptions {
  contentDir?: string;
  outputDir?: string;
  templateDir?: string;
  configFile?: string;
  plugins?: Plugin[];
  incremental?: boolean;
  clean?: boolean;
  cacheFile?: string;
  onStats?(stats: BuildStats): void;
}

export interface BuildStats {
  pagesBuilt: number;
  pagesSkipped: number;
  durationMs: number;
  timeSavedMs: number;
  cleanBuild: boolean;
}

export interface IncrementalBuildState {
  enabled: boolean;
  cleanBuild: boolean;
  skippedOutputPaths: Set<string>;
}

export interface BuildContext {
  readonly contentDir: string;
  readonly outputDir: string;
  readonly templateDir: string;
  readonly options: BuildOptions;
  pages: Page[];
  incremental: IncrementalBuildState;
  stats: BuildStats;
}

export type HookResult = void | Promise<void>;
export type FileHookResult = void | Page | Promise<void | Page>;

export interface Plugin {
  name?: string;
  onStart?(context: BuildContext): HookResult;
  beforeBuild?(context: BuildContext): HookResult;
  onFile?(page: Page, context: BuildContext): FileHookResult;
  afterBuild?(context: BuildContext): HookResult;
  onEnd?(context: BuildContext): HookResult;
}

export interface SsgConfig {
  plugins?: Plugin[];
}
