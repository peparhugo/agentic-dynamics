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
  slug: string;
  sourcePath: string;
}

export interface SiteConfig {
  sourceDir: string;
  templateDir: string;
  outputDir: string;
  siteTitle: string;
  siteUrl: string;
  port: number;
  serve: boolean;
  watch: boolean;
}

export interface TagData {
  tag: string;
  pages: Page[];
}

export interface TemplateContext {
  page?: Page;
  pages?: Page[];
  tags?: TagData[];
  site: { title: string; url: string };
  [key: string]: unknown;
}
