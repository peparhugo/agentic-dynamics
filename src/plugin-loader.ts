import fs from 'fs';
import path from 'path';
import { Plugin, PluginManager } from './plugin';

export interface PluginConfig {
  plugins: (Plugin | string)[];
}

async function loadPluginModule(pluginPath: string): Promise<Plugin> {
  if (path.isAbsolute(pluginPath)) {
    const module = await import(pluginPath);
    const DefaultExport = module.default;
    if (DefaultExport && typeof DefaultExport === 'function') {
      return new DefaultExport();
    }
    if (DefaultExport && typeof DefaultExport.name === 'string') {
      return DefaultExport;
    }
    throw new Error(`Invalid plugin module: ${pluginPath}`);
  } else {
    const module = await import(pluginPath);
    const DefaultExport = module.default;
    if (DefaultExport && typeof DefaultExport === 'function') {
      return new DefaultExport();
    }
    if (DefaultExport && typeof DefaultExport.name === 'string') {
      return DefaultExport;
    }
    throw new Error(`Invalid plugin module: ${pluginPath}`);
  }
}

export async function loadPluginsFromConfig(configPath: string): Promise<PluginManager> {
  const manager = new PluginManager();

  if (!fs.existsSync(configPath)) {
    return manager;
  }

  const configModule = await import(configPath);
  const config: PluginConfig = configModule.default || configModule;

  if (!config.plugins || !Array.isArray(config.plugins)) {
    return manager;
  }

  for (const pluginOrPath of config.plugins) {
    if (typeof pluginOrPath === 'string') {
      const plugin = await loadPluginModule(pluginOrPath);
      manager.addPlugin(plugin);
    } else if (pluginOrPath && typeof pluginOrPath === 'object' && 'name' in pluginOrPath) {
      manager.addPlugin(pluginOrPath as Plugin);
    }
  }

  return manager;
}

export function createPluginManager(plugins: Plugin[]): PluginManager {
  const manager = new PluginManager();
  for (const plugin of plugins) {
    manager.addPlugin(plugin);
  }
  return manager;
}
