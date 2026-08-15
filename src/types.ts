/**
 * Shared types for the static site generator.
 */

/** Parsed metadata for a Markdown page. */
export interface Frontmatter {
  title?: string;
  date?: string;
  tags?: string[];
  /** Page template name (without or with the `.hbs` extension). */
  template?: string;
  /** Layout template name (without or with the `.hbs` extension). */
  layout?: string;
  [key: string]: unknown;
}

/** A fully processed page ready to be rendered. */
export interface Page {
  /** Slug derived from the source file name (without extension). */
  slug: string;
  /** Absolute or relative path of the source Markdown file. */
  sourcePath: string;
  /** The HTML file name this page will be written to. */
  outputName: string;
  /** Page title (frontmatter title, falling back to the slug). */
  title: string;
  /** Publication date, if provided. */
  date?: string;
  /** List of tags, if provided. */
  tags: string[];
  /** Rendered HTML body of the page. */
  html: string;
  /** Raw Markdown body (frontmatter stripped). */
  content: string;
  /** Raw source file contents. */
  raw: string;
  /** Full parsed frontmatter data. */
  data: Frontmatter;
}

/** Options controlling how a site is built. */
export interface BuildOptions {
  /** Directory containing Markdown content files. */
  contentDir: string;
  /** Directory where generated HTML files are written. */
  outputDir: string;
  /**
   * Directory containing templates, layouts and partials
   * (default: `./templates`). When it does not exist, the built-in
   * renderers are used instead.
   */
  templatesDir?: string;
}
