export interface Frontmatter {
  title: string;
  date?: string;
  tags?: string[];
  draft?: boolean;
  layout?: string;
  [key: string]: unknown;
}

export interface Post {
  frontmatter: Frontmatter;
  content: string;
  html: string;
  slug: string;
  sourcePath: string;
}

export interface SiteConfig {
  source: string;
  output: string;
  templates: string;
  siteTitle: string;
  siteUrl: string;
  devPort: number;
}

export interface TemplateData {
  site: {
    title: string;
    url: string;
  };
  page: Frontmatter & { content: string; slug: string };
  posts?: Post[];
  tags?: { tag: string; posts: Post[] }[];
  currentTag?: string;
}
