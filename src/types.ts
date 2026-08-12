export interface Page {
  slug: string;
  title: string;
  date?: string;
  tags: string[];
  content: string;
  html: string;
}

export interface BuildOptions {
  contentDir: string;
  outputDir: string;
}
