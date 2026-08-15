export interface Page {
  /** URL-safe identifier derived from the source file path, used as the output file name. */
  slug: string;
  title: string;
  date?: string;
  tags: string[];
  /** Rendered HTML body (without the surrounding page template). */
  html: string;
  /** Path to the source Markdown file, relative to the content directory. */
  sourcePath: string;
  outputFile: string;
}
