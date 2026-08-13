export interface PageFrontmatter {
  title: string;
  date?: string;
  tags: string[];
}

export interface Page {
  /** Slug relative to the content dir, without extension, using '/' separators. */
  slug: string;
  frontmatter: PageFrontmatter;
  contentHtml: string;
  /** Absolute path to the source markdown file. */
  sourcePath: string;
}

export interface BuildOptions {
  contentDir: string;
  outputDir: string;
  /** Title used in the generated index page. */
  siteTitle?: string;
}

export interface BuildResult {
  pages: Page[];
  outputFiles: string[];
}
