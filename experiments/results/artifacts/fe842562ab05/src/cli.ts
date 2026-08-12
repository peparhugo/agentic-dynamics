#!/usr/bin/env node
import { access } from 'node:fs/promises';
import { buildSite, getLastBuildStats } from './generator';
import { startDevServer } from './dev-server';

function usage(): string {
  return 'Usage: ssg build|serve [--content <dir>] [--output <dir>] [--templates <dir>] [--incremental] [--clean] [--port <number>]';
}

function parseOptions(args: string[], allowPort = false): { contentDir?: string; outputDir?: string; templatesDir?: string; port?: number; incremental?: boolean; clean?: boolean } {
  const options: { contentDir?: string; outputDir?: string; templatesDir?: string; port?: number; incremental?: boolean; clean?: boolean } = {};
  for (let index = 0; index < args.length; index += 1) {
    const flag = args[index];
    if (flag === '--incremental') { options.incremental = true; continue; }
    if (flag === '--clean') { options.clean = true; continue; }
    if (flag !== '--content' && flag !== '--output' && flag !== '--templates' && (!allowPort || flag !== '--port')) {
      throw new Error(`Unknown option: ${flag}`);
    }
    const value = args[index + 1];
    if (!value || value.startsWith('--')) {
      throw new Error(`Missing value for ${flag}`);
    }
    if (flag === '--port') {
      const port = Number(value);
      if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error(`Invalid port: ${value}`);
      options.port = port;
    } else if (flag === '--content') options.contentDir = value;
    else if (flag === '--output') options.outputDir = value;
    else options.templatesDir = value;
    index += 1;
  }
  return options;
}

export async function run(args: string[]): Promise<void> {
  const [command, ...rest] = args;
  if (command === 'serve') {
    const options = parseOptions(rest, true);
    try {
      await access(options.contentDir || './content');
    } catch {
      throw new Error(usage());
    }
    const devServer = await startDevServer(options);
    const address = devServer.server.address();
    const port = typeof address === 'object' && address ? address.port : 3000;
    console.log(`Serving ./dist at http://localhost:${port}`);
    return;
  }
  if (command !== 'build') throw new Error(usage());
  const pages = await buildSite(parseOptions(rest));
  const stats = getLastBuildStats();
  console.log(`Built ${stats.built} page${stats.built === 1 ? '' : 's'}, skipped ${stats.skipped}; time saved ${stats.timeSavedMs}ms.`);
}

if (require.main === module) {
  run(process.argv.slice(2)).catch((error: unknown) => {
    console.error(error instanceof Error ? error.message : error);
    process.exitCode = 1;
  });
}
