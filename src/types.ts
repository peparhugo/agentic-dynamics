export interface Frontmatter {
  title?: string;
  date?: string | Date;
  tags?: string[] | string;
  template?: string;
  layout?: string;
  [key: string]: unknown;
}

export interface Page {
  title: string;
  date?: string;
  tags: string[];
  html: string;
  outputPath: string;
  url: string;
  template?: string;
  layout?: string;
  data?: Frontmatter;
}

export interface BuildOptions {
  contentDir?: string;
  outputDir?: string;
  templateDir?: string;
  configFile?: string;
  plugins?: Plugin[];
}

export interface BuildContext {
  readonly contentDir: string;
  readonly outputDir: string;
  readonly templateDir: string;
  readonly options: BuildOptions;
  pages: Page[];
}

export type HookResult = void | Promise<void>;
export type FileHookResult = void | Page | Promise<void | Page>;

export interface Plugin {
  name?: string;
  onStart?(context: BuildContext): HookResult;
  beforeBuild?(context: BuildContext): HookResult;
  onFile?(page: Page, context: BuildContext): FileHookResult;
  afterBuild?(context: BuildContext): HookResult;
  onEnd?(context: BuildContext): HookResult;
}

export interface SsgConfig {
  plugins?: Plugin[];
}
