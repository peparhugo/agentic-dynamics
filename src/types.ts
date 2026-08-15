export interface Frontmatter {
  title?: string;
  date?: Date | string;
  tags?: string[];
  template?: string;
  layout?: string;
}

export interface Page {
  slug: string;
  title: string;
  date: Date;
  tags: string[];
  html: string;
  template?: string;
  layout?: string;
  sourcePath?: string;
  sourceHash?: string;
}

export interface BuildOptions {
  contentDir: string;
  outputDir: string;
  templatesDir?: string;
  incremental?: boolean;
  clean?: boolean;
  cacheFile?: string;
}

export interface BuildStats {
  pagesBuilt: number;
  pagesSkipped: number;
  totalPages: number;
  timeSavedMs: number;
}

export interface BuildResult {
  pages: Page[];
  stats: BuildStats;
}
