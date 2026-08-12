export interface Page {
  title: string;
  slug: string;
  date?: string;
  tags: string[];
  body: string;
  html: string;
  excerpt: string;
  filePath: string;
  template?: string;
  layout?: string;
}

export interface BuildResult {
  pages: number;
  outputDir: string;
  files: string[];
  pagesBuilt: number;
  pagesSkipped: number;
  timeSavedMs: number;
}

export interface BuildStats {
  pagesBuilt: number;
  pagesSkipped: number;
  timeSavedMs: number;
}
