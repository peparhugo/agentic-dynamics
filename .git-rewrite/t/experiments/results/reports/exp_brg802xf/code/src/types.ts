export type Frontmatter = {
  title?: string;
  date?: string; // ISO or parseable
  tags?: string[];
  draft?: boolean;
  layout?: string; // layout name in templates/layouts
  template?: string; // page template name in templates/pages
  [key: string]: any;
};

export type Page = {
  sourcePath: string;
  relPath: string; // relative path under src
  outDir: string; // directory where index.html will be written
  urlPath: string; // "/foo/bar/"
  contentHtml: string;
  fm: Frontmatter;
};

export type GenerateOptions = {
  srcDir: string;
  templatesDir: string;
  outDir: string;
  includeDrafts?: boolean;
  siteUrl?: string; // for rss absolute links
  devInjectReload?: boolean;
};
