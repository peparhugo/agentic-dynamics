export interface FrontMatter {
  title?: string;
  date?: string;
  tags?: string[];
  [key: string]: unknown;
}

export interface Page {
  /** Path to the source markdown file, relative to the content directory. */
  sourcePath: string;
  /** URL-friendly slug derived from the source path, without extension. */
  slug: string;
  /** Output file name, e.g. "about.html". */
  outputFile: string;
  title: string;
  date: string | undefined;
  tags: string[];
  html: string;
}

export interface BuildOptions {
  contentDir: string;
  outputDir: string;
}

export interface BuildResult {
  pages: Page[];
  outputDir: string;
}
