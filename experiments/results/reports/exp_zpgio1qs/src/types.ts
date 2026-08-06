export type Frontmatter = {
  title?: string;
  date?: string | Date;
  tags?: string[] | string;
  draft?: boolean;
  layout?: string;
  template?: string;
  [key: string]: any;
};

export type Page = {
  sourcePath: string;
  relPath: string; // relative to src
  outPath: string; // absolute output path
  urlPath: string; // "/"-relative output path
  slug: string;
  contentHtml: string;
  data: Frontmatter & {
    title: string;
    date?: string;
    tags: string[];
    draft: boolean;
    layout: string;
    template?: string;
  };
};

export type BuildOptions = {
  srcDir: string;
  templatesDir: string;
  outDir: string;
  includeDrafts?: boolean;
  siteTitle?: string;
  siteUrl?: string; // absolute URL, e.g., https://example.com
  baseUrl?: string; // optional path prefix, no trailing slash
  liveReloadClient?: string; // script tag to inject for dev reload
};

export type BuildResult = {
  pages: Page[];
  tags: Map<string, Page[]>;
};
