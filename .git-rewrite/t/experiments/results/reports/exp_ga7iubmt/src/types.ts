export interface Frontmatter {
  title: string;
  date?: string;
  tags?: string[];
  draft?: boolean;
}

export interface Post {
  frontmatter: Frontmatter;
  content: string;
  html: string;
  slug: string;
  url: string;
  description: string;
}

export interface SiteConfig {
  title: string;
  description: string;
  url: string;
}

export interface BuildOptions {
  source: string;
  templates: string;
  output: string;
  title?: string;
  description?: string;
  url?: string;
  includeDrafts?: boolean;
}

export interface ServeOptions extends BuildOptions {
  port: string;
}
