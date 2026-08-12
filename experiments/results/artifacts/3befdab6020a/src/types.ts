export interface Frontmatter {
  title: string;
  date: string;
  tags: string[];
  template?: string;
  layout?: string;
}

export interface Page {
  slug: string;
  frontmatter: Frontmatter;
  content: string;
  html: string;
}

export interface BuildStats {
  pagesBuilt: number;
  pagesSkipped: number;
  totalPages: number;
}
