export interface PageMeta {
  title: string;
  date?: string;
  tags?: string[];
  template?: string;
  layout?: string;
}

export interface Page extends PageMeta {
  slug: string;
  content: string;
  html: string;
}
