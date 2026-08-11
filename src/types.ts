export interface Frontmatter {
  title: string;
  date?: string;
  tags?: string[];
  template?: string;
  layout?: string;
}

export interface Page {
  frontmatter: Frontmatter;
  html: string;
  slug: string;
}

export interface SSGOptions {
  contentDir: string;
  outputDir: string;
  templateDir?: string;
  incremental?: boolean;
  clean?: boolean;
}

export interface BuildStats {
  pagesBuilt: number;
  pagesSkipped: number;
}

export interface PageTemplateData {
  title: string;
  date?: string;
  dateFormatted?: string;
  tags?: string[];
  tagsStr?: string;
  content: string;
  slug: string;
}

export interface IndexTemplateData {
  title: string;
  pages: PageTemplateData[];
}
