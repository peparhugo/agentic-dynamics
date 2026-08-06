export interface Post {
  title: string;
  date: string;
  tags: string[];
  draft: boolean;
  slug: string;
  content: string;
  excerpt: string;
}

export interface SiteConfig {
  title: string;
  description: string;
  url: string;
  author: string;
}

export interface BuildContext {
  posts: Post[];
  tags: Map<string, Post[]>;
  config: SiteConfig;
}

export interface TemplateData {
  site: SiteConfig;
  posts: Post[];
  post?: Post;
  tags?: { name: string; posts: Post[] }[];
}
