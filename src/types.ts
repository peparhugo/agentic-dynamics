export interface Frontmatter {
  title: string;
  date?: string;
  tags: string[];
  template?: string;
  layout?: string;
}

export interface Page {
  sourcePath: string;
  outputPath: string;
  slug: string;
  frontmatter: Frontmatter;
  html: string;
}

export interface BuildOptions {
  contentDir?: string;
  outputDir?: string;
  templatesDir?: string;
  configFile?: string;
  plugins?: unknown[];
  incremental?: boolean;
  clean?: boolean;
  onStats?: (stats: BuildStats) => void;
}

export interface BuildStats {
  pagesBuilt: number;
  pagesSkipped: number;
  timeSavedMs: number;
  durationMs: number;
}

export interface DevServerOptions extends BuildOptions {
  port?: number;
}
