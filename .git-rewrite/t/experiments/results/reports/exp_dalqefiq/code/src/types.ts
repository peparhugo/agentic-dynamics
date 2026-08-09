export type Frontmatter = {
  title?: string;
  date?: string | Date;
  tags?: string[];
  draft?: boolean;
  layout?: string; // optional override per page
  [key: string]: any;
};

export type Page = {
  srcPath: string;
  relPath: string; // relative path within source dir
  outPath: string; // absolute output path
  urlPath: string; // path used in links (leading /)
  content: string; // rendered HTML content
  fm: Frontmatter & { title: string; date?: Date; tags: string[]; draft?: boolean };
};

export type BuildOptions = {
  srcDir: string;
  templatesDir: string;
  outDir: string;
  baseUrl?: string; // required for RSS
  includeDrafts?: boolean;
  concurrency?: number; // max parallelism
  clean?: boolean;
  liveReload?: boolean; // inject reload script tag
};

export type TemplateRenderContext = {
  page?: Page;
  pages: Page[];
  tags: Map<string, Page[]>;
  site: {
    baseUrl?: string;
    liveReload?: boolean;
  };
  content?: string; // for layout injection
};
