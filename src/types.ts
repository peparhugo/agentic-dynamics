export interface BuildOptions {
  contentDir?: string;
  outputDir?: string;
  templatesDir?: string;
  configFile?: string;
  plugins?: Plugin[];
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
