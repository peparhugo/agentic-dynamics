import { Plugin } from './src/plugin.js';
import { MarkdownPlugin } from './src/plugins/markdown-plugin.js';
import { TemplatePlugin } from './src/plugins/template-plugin.js';

export function getDefaultPlugins(): Plugin[] {
  return [
    new MarkdownPlugin(),
    new TemplatePlugin()
  ];
}

export async function loadPlugins(configPath?: string): Promise<Plugin[]> {
  if (!configPath) {
    return getDefaultPlugins();
  }

  try {
    const module = await import(configPath);
    const plugins = module.default || module.plugins || getDefaultPlugins();
    return Array.isArray(plugins) ? plugins : [plugins];
  } catch {
    console.warn(`Failed to load plugins from ${configPath}, using defaults`);
    return getDefaultPlugins();
  }
}
