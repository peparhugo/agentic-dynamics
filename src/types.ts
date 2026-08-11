export interface PageMeta {
  title: string;
  date?: string;
  tags?: string[];
}

export interface Page extends PageMeta {
  slug: string;
  content: string;
  html: string;
}
