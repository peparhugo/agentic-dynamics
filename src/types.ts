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

export interface BuildResult {
  pages: Page[];
  files: string[];
}
