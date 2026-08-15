export interface PageMeta {
  title: string;
  date?: string;
  tags: string[];
  template?: string;
}

export interface ParsedMarkdown {
  meta: PageMeta;
  content: string;
  html: string;
}

export interface Post extends PageMeta {
  slug: string;
  content: string;
  html: string;
}
