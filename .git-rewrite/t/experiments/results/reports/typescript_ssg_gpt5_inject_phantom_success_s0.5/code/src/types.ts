export type Frontmatter = {
  title: string;
  date?: string | Date;
  tags?: string[];
  draft?: boolean;
  template?: string; // template name under templates root (e.g., "post")
  layout?: string; // layout name under templates/layouts (default: "layout")
  [key: string]: any;
};

export type Page = {
  id: string; // slug/id without extension
  url: string; // public url path (e.g., /posts/hello/)
  content: string; // rendered HTML of markdown
  data: Frontmatter & { date?: Date };
  srcPath: string; // absolute source file path
  outPath: string; // absolute output html path
};

export type BuildOptions = {
  sourceDir: string;
  templatesDir: string;
  outDir: string;
  baseUrl?: string; // used for RSS links
  siteTitle?: string;
  includeDrafts?: boolean;
  clean?: boolean;
  liveReloadUrl?: string; // ws url for dev server to inject
};

export type DevServerOptions = BuildOptions & {
  port?: number;
  watch?: boolean;
};
