import path from 'path';
import { BuildOptions, buildAndWrite } from './build';
import { loadConfig } from './config';
import { SSGEngine } from './engine';
import { PluginContext } from './plugin';
import { clearTemplateEngineCache } from './templates';
import { devServerPlugin } from '../plugins/dev-server-plugin';

export interface ServeOptions extends BuildOptions {
  port?: number;
}

export interface DevServer {
  port: number;
  close(): Promise<void>;
}

const DEFAULT_PORT = 3000;

function defaultTemplatesDir(): string {
  return path.resolve(process.cwd(), 'templates');
}

export async function startServer(options: ServeOptions): Promise<DevServer> {
  const {
    contentDir,
    outputDir,
    templatesDir = defaultTemplatesDir(),
    port = DEFAULT_PORT,
  } = options;

  const ctx: PluginContext = { contentDir, outputDir, templatesDir };
  const buildPlugins = loadConfig(process.cwd()).plugins;

  let engine: SSGEngine;
  const runBuild = (): void => {
    try {
      clearTemplateEngineCache(templatesDir);
      buildAndWrite(engine, ctx);
    } catch (err) {
      console.error('Rebuild failed:', err instanceof Error ? err.message : err);
    }
  };

  const dsPlugin = devServerPlugin({ port, rebuild: runBuild });
  engine = new SSGEngine([...buildPlugins, dsPlugin]);

  runBuild();
  await engine.start(ctx);

  return {
    port: dsPlugin.getPort(),
    close: async () => {
      await engine.end(ctx);
    },
  };
}
