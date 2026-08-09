export interface PostMeta {
  title: string;
  date: string;
  tags: string[];
  draft: boolean;
}

export interface Post extends PostMeta {
  slug: string;
  html: string;
  raw: string;
}

export interface TagPage {
  tag: string;
  posts: Post[];
  html: string;
}

export interface SiteData {
  posts: Post[];
  tags: TagPage[];
  rss: string;
}
