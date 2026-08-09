export interface PostFrontmatter {
  title: string;
  date?: string;
  tags?: string[];
  draft?: boolean;
  layout?: string;
  [key: string]: unknown;
}

export interface Post {
  slug: string;
  sourcePath: string;
  frontmatter: PostFrontmatter;
  body: string;
  html: string;
  url: string;
}

export interface TagIndex {
  tag: string;
  posts: Post[];
  url: string;
}

export interface SiteConfig {
  title: string;
  description: string;
  url: string;
  author?: string;
  language?: string;
}

export interface BuildContext {
  posts: Post[];
  tags: TagIndex[];
  config: SiteConfig;
  sourceDir: string;
  templateDir: string;
  outputDir: string;
}
