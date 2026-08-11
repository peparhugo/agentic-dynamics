export interface Frontmatter {
  title: string;
  date?: string;
  tags?: string[];
  template?: string;
  layout?: string;
}

export interface Page {
  frontmatter: Frontmatter;
  content: string;
  slug: string;
  html?: string;
}

export interface BuildOptions {
  contentDir: string;
  outputDir: string;
  templatesDir?: string;
}

export interface ServeOptions {
  contentDir: string;
  outputDir: string;
  templatesDir?: string;
  port: number;
}

export interface Plugin {
  name: string;
  onStart?(ctx: PluginContext): void;
  beforeBuild?(ctx: PluginContext): void;
  onFile?(page: Page, ctx: PluginContext): void;
  afterBuild?(ctx: PluginContext): void;
  onEnd?(ctx: PluginContext): void;
}

export interface PluginContext extends Record<string, any> {
  options: BuildOptions;
  pages: Page[];
}
