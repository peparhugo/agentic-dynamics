import { DevServerPlugin } from './plugins/dev-server';
import type { ServeHandle, ServeOptions } from './plugins/dev-server';

export {
  DEFAULT_PORT,
  WS_PATH,
  RELOAD_MESSAGE,
  ServeOptions,
  ServeHandle,
  contentType,
  liveReloadScript,
  injectLiveReloadScript,
  resolveFile,
} from './plugins/dev-server';

export async function startServe(options: ServeOptions): Promise<ServeHandle> {
  const plugin = new DevServerPlugin(options);
  await plugin.start();
  return plugin.toHandle();
}

export async function serve(options: ServeOptions): Promise<void> {
  const handle = await startServe(options);
  const { port, outputDir } = options;

  console.log(`Serving ${outputDir} at http://localhost:${port}`);
  console.log(`Watching for changes...`);

  const shutdown = (): void => {
    handle.stop().then(() => process.exit(0));
  };
  process.once('SIGINT', shutdown);
  process.once('SIGTERM', shutdown);
}
