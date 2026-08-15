export interface Frontmatter {
  title?: string;
  date?: string;
  tags?: string[];
  template?: string;
  layout?: string;
}

export interface Page {
  slug: string;
  title: string;
  date?: string;
  tags: string[];
  html: string;
  sourcePath: string;
  template?: string;
  layout?: string;
  data: Record<string, unknown>;
}

export interface BuildOptions {
  contentDir: string;
  outputDir: string;
  templatesDir?: string;
}

export interface BuildResult {
  pages: Page[];
  outputDir: string;
}

export interface ServeOptions {
  contentDir: string;
  outputDir: string;
  templatesDir?: string;
  port?: number;
  host?: string;
}
