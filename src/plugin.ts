export interface BuildOptions {
  contentDir?: string;
  outputDir?: string;
  templatesDir?: string;
  configFile?: string;
  plugins?: Plugin[];
}

export interface ResolvedBuildOptions {
  contentDir: string;
  outputDir: string;
  templatesDir: string;
}

export interface Page {
  title: string;
  date?: string;
  tags: string[];
  outputPath: string;
}

export interface PluginPage extends Page {
  sourcePath: string;
  source: string;
  data: Record<string, unknown>;
  content: string;
  html: string;
}

export interface PluginContext {
  options: ResolvedBuildOptions;
  pages: PluginPage[];
  build(): Promise<Page[]>;
}

export interface Plugin {
  name?: string;
  onStart?(context: PluginContext): void | Promise<void>;
  beforeBuild?(context: PluginContext): void | Promise<void>;
  afterBuild?(context: PluginContext): void | Promise<void>;
  onFile?(page: PluginPage, context: PluginContext): void | Promise<void>;
  onEnd?(context: PluginContext): void | Promise<void>;
}

export interface SsgConfig extends BuildOptions {}

export function defineConfig(config: SsgConfig): SsgConfig {
  return config;
}
