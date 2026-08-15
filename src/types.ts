export interface PageMetadata {
  title: string;
  date?: string;
  tags: string[];
  [key: string]: unknown;
}

export interface Page {
  metadata: PageMetadata;
  html: string;
  outputPath: string;
}

/** A page while it is being processed by build plugins. */
export interface BuildPage extends Page {
  sourceFile: string;
  source: string;
  renderedHtml?: string;
}

export interface BuildOptions {
  contentDirectory?: string;
  outputDirectory?: string;
  templatesDirectory?: string;
}

export interface BuildContext {
  contentDirectory: string;
  outputDirectory: string;
  templatesDirectory: string;
  pages: BuildPage[];
}

/** Implement any hooks needed to extend a site build. Hooks run in plugin order. */
export interface Plugin {
  onStart?(context: BuildContext): void | Promise<void>;
  beforeBuild?(context: BuildContext): void | Promise<void>;
  afterBuild?(context: BuildContext): void | Promise<void>;
  onFile?(page: BuildPage, context: BuildContext): void | Promise<void>;
  onEnd?(context: BuildContext): void | Promise<void>;
}
