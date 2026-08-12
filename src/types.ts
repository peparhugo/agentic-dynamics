export interface Page {
  title: string;
  date: string;
  tags: string[];
  slug: string;
  source: string;
  html: string;
  template?: string;
  layout?: string;
  data?: Record<string, unknown>;
}

export interface BuildStats {
  total: number;
  built: number;
  skipped: number;
  timeSaved: number;
  time: number;
  incremental: boolean;
}

export interface BuildResult {
  pages: Page[];
  files: string[];
  stats?: BuildStats;
}
