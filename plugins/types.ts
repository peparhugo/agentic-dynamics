import type { Server } from 'node:http';
import type { FSWatcher } from 'chokidar';

export interface Page {
  title: string;
  date?: string;
  tags: string[];
  slug: string;
  html: string;
}

export type Metadata = Record<string, unknown>;

export interface SourcePage extends Page {
  metadata: Metadata;
  template?: string;
}

export interface BuildContext {
  contentDir: string;
  outputDir: string;
  templatesDir: string;
  files: string[];
  sourcePages: SourcePage[];
  pages: Page[];
  developmentServer?: DevelopmentServer;
}

export interface DevelopmentServer {
  server: Server;
  watcher: FSWatcher;
  close(): Promise<void>;
}

export interface Plugin {
  onStart?(context: BuildContext): Promise<void> | void;
  beforeBuild?(context: BuildContext): Promise<void> | void;
  afterBuild?(context: BuildContext): Promise<void> | void;
  onFile?(page: SourcePage, context: BuildContext): Promise<void> | void;
  onEnd?(context: BuildContext): Promise<void> | void;
}
