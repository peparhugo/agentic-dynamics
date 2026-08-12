export interface Page {
  title: string;
  date: string;
  tags: string[];
  slug: string;
  source: string;
  html: string;
}

export interface BuildResult {
  pages: Page[];
  files: string[];
}
