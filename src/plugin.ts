export interface BuildOptions {
  contentDir?: string;
  outputDir?: string;
  templatesDir?: string;
  configFile?: string | false;
  plugins?: Plugin[];
}

export interface Page {
  title: string;
  date?: string;
  tags: string[];
  sourcePath: string;
  outputPath: string;
  url: string;
}

export interface BuildPage extends Page {
  source: string;
  html: string;
  data: Record<string, unknown>;
  template?: string;
  layout?: string | false;
}

export interface BuildContext {
  readonly options: Readonly<Required<Pick<BuildOptions, 'contentDir' | 'outputDir' | 'templatesDir'>>>;
  readonly pages: BuildPage[];
  readonly initialBuild: boolean;
}

export interface Plugin {
  name?: string;
  onStart?(context: BuildContext): void | Promise<void>;
  beforeBuild?(context: BuildContext): void | Promise<void>;
  afterBuild?(context: BuildContext): void | Promise<void>;
  onFile?(page: BuildPage, context: BuildContext): void | Promise<void>;
  onEnd?(context: BuildContext): void | Promise<void>;
}

export interface SsgConfig {
  plugins?: Plugin[];
}

export function defineConfig(config: SsgConfig): SsgConfig {
  return config;
}
