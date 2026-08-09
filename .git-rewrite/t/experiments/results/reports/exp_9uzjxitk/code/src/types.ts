export interface Frontmatter {
  title: string;
  date: string;
  tags: string[];
  draft: boolean;
  layout: string;
}

export interface Post {
  slug: string;
  frontmatter: Frontmatter;
  raw: string;
  html: string;
  body: string;
}

export interface SiteConfig {
  src: string;
  templates: string;
  output: string;
  baseUrl: string;
  siteTitle: string;
  siteDescription: string;
}

export interface TemplateContext {
  title: string;
  posts: Post[];
  tags: Array<{ tag: string; posts: Post[] }>;
  site: { title: string; description: string; baseUrl: string };
  body?: string;
  page?: Post;
}
