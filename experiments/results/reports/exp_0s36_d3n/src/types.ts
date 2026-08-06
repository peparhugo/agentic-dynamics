export interface Frontmatter {
  title: string;
  date?: string;
  tags?: string[];
  draft?: boolean;
  layout?: string;
  [key: string]: unknown;
}

export interface Page {
  path: string;
  relativePath: string;
  frontmatter: Frontmatter;
  content: string;
  html: string;
  url: string;
}

export interface SiteConfig {
  title: string;
  description: string;
  url: string;
  author?: string;
  language?: string;
}

export interface TemplateContext {
  title: string;
  date?: string;
  tags?: string[];
  content: string;
  page: Page;
  pages: Page[];
  site: SiteConfig;
  [key: string]: unknown;
}

export interface TagIndexContext {
  tag: string;
  posts: Page[];
  site: SiteConfig;
  title: string;
  pages: Page[];
  [key: string]: unknown;
}

export interface CLIOptions {
  source: string;
  template: string;
  output: string;
  serve: boolean;
  port: number;
  siteConfig: string;
}
