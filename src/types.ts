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
  renderedHtml?: string;
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

export interface BuildStats {
  pagesBuilt: number;
  pagesSkipped: number;
  timeSaved: number;
  duration: number;
}

export interface IncrementalBuildState {
  readonly enabled: boolean;
  readonly cleanBuild: boolean;
  readonly changedSources: ReadonlySet<string>;
  readonly skippedSources: ReadonlySet<string>;
}

export interface BuildContext {
  readonly options: Readonly<Required<Pick<BuildOptions, 'contentDir' | 'outputDir' | 'templatesDir'>>>;
  readonly pages: GeneratedPage[];
  readonly incremental: IncrementalBuildState;
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
