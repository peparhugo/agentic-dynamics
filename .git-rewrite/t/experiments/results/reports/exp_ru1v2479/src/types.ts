export interface Post {
  slug: string;
  title: string;
  date: Date;
  tags: string[];
  draft: boolean;
  content: string;
  html: string;
  layout: string;
  [key: string]: unknown;
}

export interface SiteConfig {
  sourceDir: string;
  templateDir: string;
  outputDir: string;
  siteTitle: string;
  siteUrl: string;
  postsPerPage: number;
  includeDrafts: boolean;
  port: number;
}

export interface TemplateContext {
  site: {
    title: string;
    url: string;
  };
  page: {
    title: string;
    date?: string;
    tags?: string[];
    content?: string;
  };
  posts?: Post[];
  tags?: Array<{ name: string; count: number }>;
  body?: string;
  [key: string]: unknown;
}
