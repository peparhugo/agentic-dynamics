export interface Page {
  slug: string;
  title: string;
  date?: string;
  tags: string[];
  html: string;
  template?: string;
  layout?: string | false;
  data: Record<string, unknown>;
  sourcePath?: string;
  sourceHash?: string;
}

export interface BuildOptions {
  content?: string;
  output?: string;
  templates?: string;
  incremental?: boolean;
  clean?: boolean;
}

export interface BuildStats {
  pagesBuilt: number;
  pagesSkipped: number;
  timeSavedMs: number;
}

export type BuildPages = Page[] & { buildStats: BuildStats };

export interface PluginContext {
  options: BuildOptions;
  contentDirectory: string;
  outputDirectory: string;
  templatesDirectory: string;
  pages: Page[];
  page?: Page;
  html?: string;
}

export interface Plugin {
  onStart?(context: PluginContext): void | Promise<void>;
  beforeBuild?(context: PluginContext): void | Promise<void>;
  afterBuild?(context: PluginContext): void | Promise<void>;
  onFile?(page: Page, context: PluginContext): void | Promise<void>;
  onEnd?(context: PluginContext): void | Promise<void>;
}
