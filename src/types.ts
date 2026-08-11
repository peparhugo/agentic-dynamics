export interface Frontmatter {
  title: string;
  date: string;
  tags: string[];
}

export interface Page {
  slug: string;
  frontmatter: Frontmatter;
  content: string;
  html: string;
}
