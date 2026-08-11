export interface Frontmatter {
  title: string;
  date?: string;
  tags?: string[];
}

export interface Page {
  frontmatter: Frontmatter;
  html: string;
  slug: string;
}

export interface SSGOptions {
  contentDir: string;
  outputDir: string;
}
