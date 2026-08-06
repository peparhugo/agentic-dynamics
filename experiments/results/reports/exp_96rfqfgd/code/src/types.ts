export interface Frontmatter {
  title: string;
  date?: string;
  tags?: string[];
  draft?: boolean;
  [key: string]: unknown;
}

export interface Page {
  path: string;
  frontmatter: Frontmatter;
  content: string;
  html: string;
  url: string;
}

export interface SiteConfig {
  sourceDir: string;
  templateDir: string;
  outputDir: string;
  siteTitle?: string;
  siteUrl?: string;
  siteDescription?: string;
}

export interface TemplateContext {
  body?: string;
  page?: Page;
  pages: Page[];
  tag?: string;
  site: {
    title?: string;
    description?: string;
    url?: string;
  };
}
