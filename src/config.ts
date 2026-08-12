import * as fs from 'fs';
import * as path from 'path';
import type { Plugin } from './plugin';
import { MarkdownPlugin } from './plugins/markdown-plugin';
import { TemplatePlugin } from './plugins/template-plugin';

export const DEFAULT_CONFIG_FILE = 'ssg.config.ts';

export interface SsgConfig {
  plugins: Plugin[];
  [key: string]: unknown;
}

export function builtinPlugins(): Plugin[] {
  return [new MarkdownPlugin(), new TemplatePlugin()];
}

function normalizeConfig(loaded: unknown): SsgConfig {
  const config = (loaded && typeof loaded === 'object' && 'default' in (loaded as Record<string, unknown>)
    ? (loaded as Record<string, unknown>).default
    : loaded) as Record<string, unknown> | null | undefined;

  const rawPlugins = config && Array.isArray(config.plugins) ? config.plugins : [];
  const plugins: Plugin[] = rawPlugins.filter(
    (plugin): plugin is Plugin => typeof plugin === 'object' && plugin !== null && typeof (plugin as Plugin).name === 'string'
  );

  return { ...(config ?? {}), plugins: plugins.length > 0 ? plugins : builtinPlugins() };
}

export async function loadConfig(configPath?: string): Promise<SsgConfig> {
  const resolved = configPath
    ? path.resolve(configPath)
    : path.resolve(process.cwd(), DEFAULT_CONFIG_FILE);

  if (!fs.existsSync(resolved)) {
    return { plugins: builtinPlugins() };
  }

  try {
    return normalizeConfig(require(resolved));
  } catch {
    const jsPath = resolved.endsWith('.ts') ? `${resolved.slice(0, -3)}.js` : null;
    if (jsPath && fs.existsSync(jsPath)) {
      try {
        return normalizeConfig(require(jsPath));
      } catch {
        // fall through to built-ins below
      }
    }
    console.warn(`Failed to load config from ${resolved}; using built-in plugins`);
    return { plugins: builtinPlugins() };
  }
}

export async function loadPlugins(configPath?: string): Promise<Plugin[]> {
  const config = await loadConfig(configPath);
  return Array.isArray(config.plugins) && config.plugins.length > 0
    ? config.plugins
    : builtinPlugins();
}
