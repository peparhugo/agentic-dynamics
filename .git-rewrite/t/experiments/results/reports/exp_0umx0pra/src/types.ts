export interface Frontmatter {
  title: string;
  date?: string;
  tags?: string[] | string;
  draft?: boolean;
  template?: string;
  layout?: string;
  [key: string]: unknown;
}

export interface PageData {
  frontmatter: Frontmatter;
  markdown: string;
  html: string;
  sourcePath: string;
  relativePath: string;
  outputPath: string;
  url: string;
  slug: string;
  tags: string[];
  isDraft: boolean;
}

export interface SiteConfig {
  sourceDir: string;
  templateDir: string;
  outputDir: string;
  devMode: boolean;
  port: number;
  includeDrafts: boolean;
  siteTitle: string;
  siteUrl: string;
}

export interface TemplateContext {
  page: PageData;
  pages: PageData[];
  site: SiteConfig;
  body?: string;
  content?: string;
  [key: string]: unknown;
}
