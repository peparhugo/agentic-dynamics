import path from 'path';
import type { Plugin } from './plugin';
import type { SsgConfig } from './config';
import { loadConfig, loadConfigFile, resolvePlugins } from './config';
import { SsgEngine } from './engine';
import { DevServerPlugin } from './plugins/devServer';
import { liveReloadScript, injectLiveReload } from './liveReload';

export { liveReloadScript, injectLiveReload };

export interface ServeOptions {
  content: string;
  output: string;
  templates?: string;
  port?: number;
  config?: string | false;
  plugins?: Plugin[];
}

export interface DevServer {
  port: number;
  reload(): void;
  close(): Promise<void>;
}

async function resolveServeConfig(
  options: ServeOptions
): Promise<{ config: SsgConfig; baseDir: string }> {
  if (options.config === false) {
    return { config: {}, baseDir: process.cwd() };
  }
  if (typeof options.config === 'string') {
    const filePath = path.resolve(options.config);
    return { config: await loadConfigFile(filePath), baseDir: path.dirname(filePath) };
  }
  const cwd = process.cwd();
  return { config: await loadConfig(cwd), baseDir: cwd };
}

export async function serve(options: ServeOptions): Promise<DevServer> {
  const { config, baseDir } = await resolveServeConfig(options);
  const configPlugins = await resolvePlugins(config.plugins, baseDir);
  const plugins = [...configPlugins, ...(options.plugins ?? [])];

  const engine = new SsgEngine(options, config, plugins);
  const devServer = new DevServerPlugin(engine);
  return devServer.start(options);
}
