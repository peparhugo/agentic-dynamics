export interface PageData {
  title?: string;
  date?: string;
  tags?: string[];
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
}
