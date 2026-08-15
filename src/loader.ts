import * as path from 'path';
import { loadTsModule } from './module-loader';
import { Plugin, SsgConfig } from './plugin';
import { MarkdownPlugin } from '../plugins/markdown';
import { TemplatePlugin } from '../plugins/templates';

export const PLUGIN_DIR = 'plugins';

function resolvePluginFile(entry: string): string {
  const base = path.join(path.resolve(process.cwd(), PLUGIN_DIR), entry);
  return path.extname(base) ? base : `${base}.ts`;
}

function instantiate(entry: string): Plugin {
  let resolved: unknown;
  try {
    resolved = loadTsModule(resolvePluginFile(entry));
  } catch {
    throw new Error(`plugin not found: ${entry}`);
  }
  if (typeof resolved === 'function') {
    return new (resolved as new () => Plugin)();
  }
  if (resolved && typeof resolved === 'object') {
    return resolved as Plugin;
  }
  throw new Error(`plugin not found: ${entry}`);
}

/**
 * Build the plugin list. Built-in plugins (markdown, templates) are always
 * registered first; plugins configured in `ssg.config.ts` are appended in
 * order, so every hook runs across all of them sequentially.
 */
export async function loadPlugins(config: SsgConfig): Promise<Plugin[]> {
  const plugins: Plugin[] = [new MarkdownPlugin(), new TemplatePlugin()];

  const configured = config.plugins ?? [];
  for (const entry of configured) {
    if (typeof entry === 'string') {
      plugins.push(instantiate(entry));
    } else if (entry) {
      plugins.push(entry);
    }
  }

  return plugins;
}
