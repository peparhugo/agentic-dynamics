import { promises as fs } from 'fs';
import path from 'path';
import type { Plugin } from './plugin';
import { MarkdownPlugin } from './plugins/markdown';
import { TemplatePlugin } from './plugins/template';

export interface SSGConfig {
  plugins?: Array<string | Plugin | (() => Plugin)>;
  [key: string]: unknown;
}

export interface BuildOptions {
  config?: string | SSGConfig;
  plugins?: Plugin[];
}

async function fileExists(file: string): Promise<boolean> {
  try {
    await fs.access(file);
    return true;
  } catch {
    return false;
  }
}

function loadModule<T>(file: string): T {
  // eslint-disable-next-line @typescript-eslint/no-var-requires
  const mod = require(file) as unknown;
  if (mod && typeof mod === 'object') {
    const record = mod as Record<string, unknown>;
    if ('default' in record) {
      return record.default as T;
    }
  }
  return mod as T;
}

export function createBuiltInPlugins(): Plugin[] {
  return [new MarkdownPlugin(), new TemplatePlugin()];
}

export async function loadConfig(cwd: string = process.cwd()): Promise<SSGConfig> {
  const candidates = ['ssg.config.ts', 'ssg.config.js', 'ssg.config.cjs', 'ssg.config.json'];
  for (const name of candidates) {
    const file = path.join(cwd, name);
    if (await fileExists(file)) {
      if (name === 'ssg.config.json') {
        const raw = await fs.readFile(file, 'utf8');
        return JSON.parse(raw) as SSGConfig;
      }
      return loadModule<SSGConfig>(file);
    }
  }
  return {};
}

export function loadPlugin(
  entry: string | Plugin | (() => Plugin),
  baseDir: string = process.cwd()
): Plugin {
  if (typeof entry === 'function') {
    return (entry as () => Plugin)();
  }
  if (typeof entry === 'string') {
    const resolved = path.resolve(baseDir, entry);
    const mod = loadModule<Plugin | (() => Plugin)>(resolved);
    return typeof mod === 'function' ? (mod as () => Plugin)() : (mod as Plugin);
  }
  return entry;
}

export function loadUserPlugins(config: SSGConfig, baseDir: string = process.cwd()): Plugin[] {
  const plugins: Plugin[] = [];
  for (const entry of config.plugins ?? []) {
    plugins.push(loadPlugin(entry, baseDir));
  }
  return plugins;
}

export async function resolveConfig(options: BuildOptions = {}): Promise<SSGConfig> {
  if (options.config === undefined) {
    return loadConfig();
  }
  if (typeof options.config === 'string') {
    return loadModule<SSGConfig>(path.resolve(process.cwd(), options.config));
  }
  return options.config;
}
