export interface FrontMatter {
  title?: string;
  date?: string;
  tags?: string[];
  /** Name of the layout template (in templates/layouts/) to render this page with. */
  template?: string;
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
  /** Layout name from frontmatter, e.g. "post". Falls back to "default" when absent. */
  template: string | undefined;
}

export interface BuildOptions {
  contentDir: string;
  outputDir: string;
  /**
   * Directory containing Handlebars layouts/partials (see templates/README).
   * When omitted, pages render with the built-in default markup only.
   */
  templatesDir?: string;
}

export interface BuildResult {
  pages: Page[];
  outputDir: string;
}
