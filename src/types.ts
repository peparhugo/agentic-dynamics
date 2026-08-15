export interface Frontmatter {
  title?: string;
  date?: string;
  tags?: string[];
  [key: string]: unknown;
}

export interface ParsedMarkdown {
  data: Frontmatter;
  content: string;
  html: string;
}

export interface GeneratedPage extends ParsedMarkdown {
  sourcePath: string;
  outputPath: string;
  url: string;
  title: string;
}

export interface BuildOptions {
  contentDir?: string;
  outputDir?: string;
  templatesDir?: string;
  configFile?: string;
  plugins?: Plugin[];
}

export interface BuildContext {
  readonly options: Readonly<Required<Pick<BuildOptions, 'contentDir' | 'outputDir' | 'templatesDir'>>>;
  readonly pages: GeneratedPage[];
}

export type PluginHook = void | Promise<void>;

export interface Plugin {
  name?: string;
  onStart?(context: BuildContext): PluginHook;
  beforeBuild?(context: BuildContext): PluginHook;
  afterBuild?(context: BuildContext): PluginHook;
  onFile?(page: GeneratedPage, context: BuildContext): PluginHook;
  onEnd?(context: BuildContext): PluginHook;
}

export interface SsgConfig {
  plugins?: Plugin[];
}
