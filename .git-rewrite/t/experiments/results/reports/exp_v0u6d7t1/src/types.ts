export interface Frontmatter {
  title: string;
  date?: string;
  tags?: string[];
  draft?: boolean;
  layout?: string;
  [key: string]: unknown;
}

export interface Page {
  frontmatter: Frontmatter;
  content: string;
  html: string;
  sourcePath: string;
  outputPath: string;
  url: string;
  tags: string[];
  isDraft: boolean;
}

export interface BuildContext {
  pages: Page[];
  publishedPages: Page[];
  tagMap: Map<string, Page[]>;
  siteTitle: string;
  siteUrl: string;
}

export interface CLIOptions {
  source: string;
  templates: string;
  output: string;
  serve: boolean;
  port: number;
  siteTitle: string;
  siteUrl: string;
}
