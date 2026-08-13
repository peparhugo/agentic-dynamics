import { loadPlugins } from './config.js';
import { SsgEngine } from './engine.js';
import { MarkdownPlugin } from './plugins/markdown.js';
import { TemplatePlugin } from './plugins/template.js';
import { DevServerPlugin } from './plugins/dev-server.js';
import type { BuildOptions } from './plugin.js';

export interface ServeOptions extends BuildOptions {
  port?: number;
}

export interface DevServer {
  port: number;
  close(): Promise<void>;
}

export { DevServerPlugin } from './plugins/dev-server.js';

export async function startDevServer(options: ServeOptions = {}): Promise<DevServer> {
  const devServer = new DevServerPlugin(options.port);
  const plugins = [new MarkdownPlugin(), ...loadPlugins(options.configFile), ...(options.plugins ?? []),
    new TemplatePlugin(), devServer];
  const engine = new SsgEngine(options, plugins);
  devServer.setRebuild(() => engine.build().then(() => undefined));
  try {
    await engine.build();
  } catch (error) {
    await engine.end();
    throw error;
  }
  return {
    port: devServer.getPort(),
    close: () => engine.end()
  };
}
