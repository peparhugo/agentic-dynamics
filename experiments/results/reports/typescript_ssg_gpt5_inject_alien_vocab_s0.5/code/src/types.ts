export type Frontmatter = {
  title?: string;
  date?: string | Date;
  tags?: string[];
  draft?: boolean;
  layout?: string;
  template?: string;
  [key: string]: unknown;
};

export type Doc = {
  id: string; // relative path without extension
  srcPath: string;
  outPath: string; // absolute HTML output path
  url: string; // URL path starting with '/'
  frontmatter: Frontmatter & { title: string; date?: Date; tags: string[]; draft: boolean };
  body: string; // HTML
  rawBody: string; // raw markdown (no frontmatter)
  isPost: boolean;
};

export type BuildOptions = {
  srcDir: string;
  templatesDir: string;
  outDir: string;
  siteTitle?: string;
  siteUrl?: string; // e.g. https://example.com (no trailing slash)
  dev?: boolean; // inject live reload
};

export type SiteData = {
  title: string;
  url?: string;
  docs: Doc[];
  posts: Doc[];
  tags: Map<string, Doc[]>;
};
