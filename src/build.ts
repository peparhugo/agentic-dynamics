import path from 'path';
import type { BuildOptions, BuildStats, Page } from './types';
import type { Plugin } from './plugin';
import type { SsgConfig } from './config';
import { loadConfig, loadConfigFile, resolvePlugins } from './config';
import { SsgEngine } from './engine';

export interface BuildInput extends BuildOptions {
  plugins?: Plugin[];
}

export interface BuildResult {
  pages: Page[];
  stats: BuildStats;
}

async function resolveBuildConfig(
  options: BuildInput
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

export async function buildWithStats(options: BuildInput): Promise<BuildResult> {
  const { config, baseDir } = await resolveBuildConfig(options);
  const configPlugins = await resolvePlugins(config.plugins, baseDir);
  const plugins = [...configPlugins, ...(options.plugins ?? [])];

  const engine = new SsgEngine(options, config, plugins);
  const pages = await engine.run();
  return { pages, stats: engine.buildStats };
}

export async function build(options: BuildInput): Promise<Page[]> {
  const { pages } = await buildWithStats(options);
  return pages;
}
