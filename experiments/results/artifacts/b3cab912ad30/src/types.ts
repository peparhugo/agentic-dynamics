export type Frontmatter = Record<string, string>;

export interface PageData {
  path: string;
  frontmatter: Frontmatter;
  html: string;
}

export interface BuildOptions {
  contentDir: string;
  outputDir: string;
  templatesDir?: string;
  incremental?: boolean;
  clean?: boolean;
}

export interface BuildStats {
  pagesBuilt: number;
  pagesSkipped: number;
  timeSavedMs: number;
}
