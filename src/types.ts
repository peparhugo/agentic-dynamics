export interface PageFrontmatter {
  title: string;
  date?: string;
  tags: string[];
  /** Name of the template (in the templates dir) used to render this page's body. Defaults to 'page'. */
  template?: string;
  /** Name of the layout (in templates/layouts) this page's rendered body is wrapped in. Defaults to 'default'. */
  layout?: string;
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
  /** Directory containing page/index templates, templates/layouts, and templates/partials. Defaults to './templates'. */
  templatesDir?: string;
}

export interface BuildResult {
  pages: Page[];
  outputFiles: string[];
}
