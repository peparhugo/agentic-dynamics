export interface Page {
  slug: string;
  title: string;
  date?: string;
  tags: string[];
  html: string;
  template?: string;
  layout?: string | false;
  data: Record<string, unknown>;
}

export interface BuildOptions {
  content?: string;
  output?: string;
  templates?: string;
}

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
