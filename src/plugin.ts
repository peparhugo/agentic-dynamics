export interface PageMetadata {
  title: string;
  date?: string;
  tags: string[];
}

export interface GeneratedPage extends PageMetadata {
  sourcePath: string;
  outputPath: string;
  url: string;
}

export interface BuildOptions {
  contentDir?: string;
  outputDir?: string;
  templatesDir?: string;
  configFile?: string;
  plugins?: Plugin[];
  incremental?: boolean;
  clean?: boolean;
}

export interface ResolvedBuildOptions {
  contentDir: string;
  outputDir: string;
  templatesDir: string;
  configFile: string;
  incremental: boolean;
  clean: boolean;
}

export interface BuildStats {
  pagesBuilt: number;
  pagesSkipped: number;
  durationMs: number;
  timeSavedMs: number;
}

export interface Page extends GeneratedPage {
  source: string;
  content: string;
  data: Record<string, unknown>;
  body: string;
  html: string;
}

export interface BuildContext {
  options: ResolvedBuildOptions;
  pages: Page[];
  stats: BuildStats;
}

export interface Plugin {
  name?: string;
  onStart?(context: BuildContext): void | Promise<void>;
  beforeBuild?(context: BuildContext): void | Promise<void>;
  afterBuild?(context: BuildContext): void | Promise<void>;
  onFile?(page: Page, context: BuildContext): void | Promise<void>;
  onEnd?(context: BuildContext): void | Promise<void>;
}

export interface SsgConfig {
  plugins?: Plugin[];
}

export function defineConfig(config: SsgConfig): SsgConfig {
  return config;
}
