import { Frontmatter } from './markdown';

export interface Page {
  slug: string;
  title: string;
  date: string | null;
  tags: string[];
  html: string;
  rendered: string;
  template: string | null;
  layout: string | null;
  frontmatter: Frontmatter;
  sourcePath: string;
  outputPath: string;
}

export interface BuildOptions {
  contentDir: string;
  outputDir: string;
  templatesDir?: string;
  plugins?: Plugin[];
}

export interface BuildResult {
  pages: Page[];
  outputDir: string;
  indexPath: string;
}

export interface Plugin {
  name?: string;
  onStart?(): void;
  beforeBuild?(): void;
  afterBuild?(): void;
  onFile?(page: Page): void;
  onEnd?(): void;
}
