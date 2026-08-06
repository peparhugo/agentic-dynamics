export interface Frontmatter {
  title: string;
  date?: string;
  tags?: string[];
  draft?: boolean;
  slug?: string;
  [key: string]: unknown;
}

export interface Page {
  frontmatter: Frontmatter;
  content: string;
  html: string;
  slug: string;
  sourcePath: string;
}

export interface BuildContext {
  pages: Page[];
  tags: Map<string, Page[]>;
  siteTitle: string;
  siteUrl: string;
  siteDescription: string;
}

export interface CLIOptions {
  src: string;
  templates: string;
  output: string;
  serve: boolean;
  port: number;
  siteTitle: string;
  siteUrl: string;
  siteDescription: string;
}
