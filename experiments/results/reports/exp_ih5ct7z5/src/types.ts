export interface Frontmatter {
  title: string;
  date?: string;
  tags: string[];
  draft?: boolean;
  [key: string]: unknown;
}

export interface Post {
  slug: string;
  frontmatter: Frontmatter;
  content: string;
  html: string;
  url: string;
}

export interface SiteConfig {
  title: string;
  description: string;
  baseUrl: string;
}

export interface SiteData {
  posts: Post[];
  tags: Record<string, Post[]>;
  config: SiteConfig;
}

export interface CliOptions {
  source: string;
  templates: string;
  output: string;
  serve: boolean;
  port: number;
  config: SiteConfig;
}
