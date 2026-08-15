import fs from 'fs';
import path from 'path';
import { Plugin } from './plugin';
import { markdownPlugin } from '../plugins/markdown-plugin';
import { templatePlugin } from '../plugins/template-plugin';

export interface SSGConfig {
  plugins: Plugin[];
}

const DEFAULT_CONFIG_FILE = 'ssg.config.ts';

function defaultPlugins(): Plugin[] {
  return [markdownPlugin(), templatePlugin()];
}

/**
 * Requires a `.ts` config file. Under ts-jest/ts-node (as in this project's
 * own tests and `npm start`) a TypeScript require hook is already active, so
 * this succeeds directly. Under the plain compiled CLI (`dist-bin/cli.js`),
 * Node has no such hook, so the first attempt throws a SyntaxError on the
 * raw `import` syntax; in that case we lazily register ts-node and retry.
 */
function requireConfigModule(configPath: string): unknown {
  try {
    return require(configPath);
  } catch (err) {
    if (!(configPath.endsWith('.ts') && err instanceof SyntaxError)) {
      throw err;
    }
    require('ts-node/register/transpile-only');
    return require(configPath);
  }
}

/**
 * Loads the build-time plugin pipeline from `ssg.config.ts` in `cwd`. Falls
 * back to the built-in markdown + template plugins when no config file is
 * present, when it doesn't export a plugin list, or when its TypeScript
 * source can't be loaded (e.g. ts-node isn't installed), so `ssg build`
 * keeps working without any project scaffolding.
 */
export function loadConfig(cwd: string, configFile: string = DEFAULT_CONFIG_FILE): SSGConfig {
  const configPath = path.resolve(cwd, configFile);
  if (!fs.existsSync(configPath)) {
    return { plugins: defaultPlugins() };
  }

  let required: unknown;
  try {
    required = requireConfigModule(configPath);
  } catch (err) {
    console.warn(
      `ssg: could not load ${configFile} (${err instanceof Error ? err.message : err}); using built-in plugins instead.`
    );
    return { plugins: defaultPlugins() };
  }

  const config = (required as { default?: Partial<SSGConfig> } & Partial<SSGConfig>)?.default ?? required;
  const plugins = (config as Partial<SSGConfig> | undefined)?.plugins;
  return { plugins: Array.isArray(plugins) && plugins.length > 0 ? plugins : defaultPlugins() };
}
