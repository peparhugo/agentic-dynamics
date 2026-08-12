export interface PageData {
  title?: string;
  date?: string;
  tags?: string[];
  template?: string;
  layout?: string;
}

export interface Page {
  slug: string;
  content: string;
  html: string;
  data: PageData;
}

export interface BuildOptions {
  contentDir: string;
  outputDir: string;
  templatesDir?: string;
}

export interface IncrementalBuildOptions {
  incremental?: boolean;
  clean?: boolean;
}

export interface BuildStats {
  total: number;
  built: number;
  skipped: number;
  timeMs: number;
  timeSavedMs: number;
  usedCache: boolean;
}
