export interface GeneratedPage {
  title: string;
  date?: string;
  tags: string[];
  sourcePath: string;
  outputPath: string;
  url: string;
}

export interface PluginPage extends GeneratedPage {
  source: string;
  content: string;
  html: string;
  output: string;
  frontmatter: Record<string, unknown>;
  template?: string;
  layout?: string;
}

export interface PluginContext {
  contentDir: string;
  outputDir: string;
  templatesDir: string;
  pages: PluginPage[];
}

export interface Plugin {
  onStart?(context: PluginContext): void | Promise<void>;
  beforeBuild?(context: PluginContext): void | Promise<void>;
  afterBuild?(context: PluginContext): void | Promise<void>;
  onFile?(page: PluginPage, context: PluginContext): void | Promise<void>;
  onEnd?(context: PluginContext): void | Promise<void>;
}

export interface SsgConfig {
  plugins?: Plugin[];
}

export interface BuildOptions {
  contentDir?: string;
  outputDir?: string;
  templatesDir?: string;
  configFile?: string;
  plugins?: Plugin[];
}
