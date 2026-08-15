import * as path from 'path';
import { SsgEngine } from './engine';
import { defaultBuildPlugins } from './generator';
import { DevServerPlugin } from '../plugins/dev-server';
import type { BuildOptions } from './generator';

export interface ServeOptions extends BuildOptions {
  /** Port to listen on. Use 0 to let the OS assign an ephemeral port. Defaults to 3000. */
  port?: number;
  /** Delay (ms) between a watched file change and the triggered rebuild, to coalesce bursts of changes. */
  debounceMs?: number;
}

export interface ServeHandle {
  port: number;
  url: string;
  close(): Promise<void>;
}

const DEFAULT_PORT = 3000;
const DEFAULT_DEBOUNCE_MS = 100;

/**
 * Starts a dev server that serves the built site from `outputDir`, rebuilds
 * whenever `contentDir` or `templatesDir` change, and pushes a live-reload
 * notification over WebSocket to connected pages so browsers refresh
 * automatically once the rebuild completes.
 */
export function serve(options: ServeOptions): Promise<ServeHandle> {
  const { contentDir, outputDir } = options;
  const templatesDir = options.templatesDir ?? path.resolve(process.cwd(), 'templates');
  const debounceMs = options.debounceMs ?? DEFAULT_DEBOUNCE_MS;

  const devServer = new DevServerPlugin();
  const engine = new SsgEngine({
    contentDir,
    outputDir,
    templatesDir,
    plugins: [...defaultBuildPlugins(), devServer],
  });

  engine.build();

  return devServer.start({
    outputDir,
    watchPaths: [contentDir, templatesDir],
    port: options.port ?? DEFAULT_PORT,
    debounceMs,
    rebuild: () => {
      engine.build();
    },
  });
}
