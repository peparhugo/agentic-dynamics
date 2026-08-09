export interface Frontmatter {
  title: string;
  date?: string | Date;
  tags?: string[];
  draft?: boolean;
  layout?: string;
  [key: string]: unknown;
}

export interface Post {
  slug: string;
  frontmatter: Frontmatter;
  content: string;
  html: string;
  excerpt?: string;
}

export interface SiteData {
  posts: Post[];
  tags: Record<string, Post[]>;
  site: {
    title: string;
    description: string;
    url: string;
  };
}

export interface BuildOptions {
  source: string;
  templates: string;
  output: string;
  drafts: boolean;
  siteTitle: string;
  siteDescription: string;
  siteUrl: string;
}

export interface ServerOptions {
  port: number;
  output: string;
}
