export type Frontmatter = Record<string, string>;

export interface PageData {
  path: string;
  frontmatter: Frontmatter;
  html: string;
}
