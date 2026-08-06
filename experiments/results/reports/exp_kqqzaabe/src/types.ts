export interface Frontmatter {
  title: string;
  date?: string;
  tags?: string[];
  draft?: boolean;
  layout?: string;
  [key: string]: unknown;
}

export interface Page {
  frontmatter: Frontmatter;
  rawContent: string;
  html: string;
  slug: string;
  sourcePath: string;
}

export interface TemplateSet {
  render(templateName: string, data: Record<string, unknown>): string;
  getLayoutNames(): string[];
}

export interface GeneratorConfig {
  sourceDir: string;
  templateDir: string;
  outputDir: string;
  siteUrl?: string;
}

export interface DevConfig extends GeneratorConfig {
  port: number;
}

export interface TagMap {
  [tag: string]: Page[];
}
