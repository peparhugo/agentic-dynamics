import * as path from 'path';
import * as fs from 'fs';
import { Plugin, PluginConfig } from './plugin.js';

export async function loadConfig(configPath: string): Promise<Plugin[]> {
  const resolvedPath = path.resolve(configPath);
  const tsDist = resolvedPath.replace(/\.ts$/, '.js');

  if (!fs.existsSync(tsDist)) {
    return [];
  }

  try {
    const module = await import(tsDist);
    const config: PluginConfig = module.default || module;

    if (!config.plugins || !Array.isArray(config.plugins)) {
      return [];
    }

    const plugins: Plugin[] = [];
    for (const pluginOrPath of config.plugins) {
      if (typeof pluginOrPath === 'string') {
        const pluginModule = await import(pluginOrPath);
        const pluginClass = pluginModule.default || pluginModule;
        plugins.push(new pluginClass());
      } else {
        plugins.push(pluginOrPath as Plugin);
      }
    }

    return plugins;
  } catch (error) {
    return [];
  }
}
