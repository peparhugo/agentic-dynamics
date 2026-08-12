export interface Page {
  slug: string;
  title: string;
  date?: string;
  tags: string[];
  content: string;
  html: string;
  template?: string;
  layout?: string;
  data?: Record<string, unknown>;
}

export interface BuildOptions {
  contentDir: string;
  outputDir: string;
  templateDir?: string;
}
