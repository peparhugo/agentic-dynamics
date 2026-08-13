export interface BuildOptions {
  contentDir?: string;
  outputDir?: string;
  templatesDir?: string;
  configFile?: string;
}

export interface Page {
  title: string;
  date?: string;
  tags: string[];
  outputPath: string;
  url: string;
}

export interface PluginPage extends Page {
  filePath: string;
  source: string;
  data: Record<string, unknown>;
  content: string;
  output: string;
}

export interface PluginContext {
  options: Required<Pick<BuildOptions, 'contentDir' | 'outputDir' | 'templatesDir'>>;
  pages: PluginPage[];
  build(): Promise<Page[]>;
}

export interface Plugin {
  name?: string;
  onStart?(context: PluginContext): void | Promise<void>;
  beforeBuild?(context: PluginContext): void | Promise<void>;
  afterBuild?(context: PluginContext): void | Promise<void>;
  onFile?(page: PluginPage): void | Promise<void>;
  onEnd?(context: PluginContext): void | Promise<void>;
}

export interface SsgConfig {
  plugins?: Plugin[];
}
