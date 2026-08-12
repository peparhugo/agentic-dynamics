export interface Frontmatter {
  title?: string;
  date?: string;
  tags: string[];
  template?: string;
  layout?: string;
}

export interface Page {
  slug: string;
  source: string;
  title: string;
  date?: string;
  tags: string[];
  body: string;
  html: string;
  template?: string;
  layout?: string;
}

export interface BuildOptions {
  contentDir: string;
  outputDir: string;
  templateDir?: string;
}
