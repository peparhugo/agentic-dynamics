export interface Page {
  slug: string;
  title: string;
  date?: string;
  tags: string[];
  content: string;
  html: string;
  sourcePath: string;
  template?: string;
  layout?: string;
  data?: Record<string, unknown>;
}

export interface BuildOptions {
  contentDir: string;
  outputDir: string;
  templatesDir?: string;
}

export interface ParsedFrontmatter {
  title?: string;
  date?: string;
  tags?: string[];
  [key: string]: unknown;
}
