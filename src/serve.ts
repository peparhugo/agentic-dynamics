import * as http from 'http';
import { build } from './build';
import { injectReloadScript, DevServerPlugin } from '../plugins/dev-server-plugin';

export { injectReloadScript } from '../plugins/dev-server-plugin';

export interface ServeOptions {
  content?: string;
  output?: string;
  templates?: string;
  port?: number;
}

export function serve(options: ServeOptions): http.Server {
  const contentDir = options.content || './content';
  const outputDir = options.output || './dist';
  const templatesDir = options.templates || './templates';
  const port = options.port || 3000;

  const devPlugin = new DevServerPlugin();

  build(contentDir, outputDir, templatesDir);

  devPlugin.setContext!({
    contentDir,
    outputDir,
    templatesDir,
  });
  devPlugin.onStart!();

  return devPlugin.listen(port);
}
