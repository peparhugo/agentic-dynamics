#!/usr/bin/env node
import { buildSite } from './generator';
import { startDevServer } from './dev-server';

function usage(): string {
  return 'Usage: ssg <build|serve> [--content <dir>] [--output <dir>] [--templates <dir>] [--incremental] [--clean] [--port <number>]';
}

export function parseArgs(args: string[]): { command: string; contentDir?: string; outputDir?: string; templatesDir?: string; incremental?: boolean; clean?: boolean; port?: number } {
  const [command, ...flags] = args;
  const options: { command: string; contentDir?: string; outputDir?: string; templatesDir?: string; incremental?: boolean; clean?: boolean; port?: number } = { command: command || '' };
  for (let index = 0; index < flags.length; index += 1) {
    const flag = flags[index];
    if (flag === '--incremental') options.incremental = true;
    else if (flag === '--clean') options.clean = true;
    else if (flag === '--content' || flag === '--output' || flag === '--templates' || flag === '--port') {
      const value = flags[++index];
      if (!value) throw new Error(`${flag} requires a value`);
      if (flag === '--content') options.contentDir = value;
      else if (flag === '--output') options.outputDir = value;
      else if (flag === '--templates') options.templatesDir = value;
      else options.port = parsePort(value);
    } else if (flag.startsWith('--content=')) options.contentDir = flag.slice('--content='.length);
    else if (flag.startsWith('--output=')) options.outputDir = flag.slice('--output='.length);
    else if (flag.startsWith('--templates=')) options.templatesDir = flag.slice('--templates='.length);
    else if (flag.startsWith('--port=')) options.port = parsePort(flag.slice('--port='.length));
    else throw new Error(`Unknown option: ${flag}`);
  }
  return options;
}

function parsePort(value: string): number {
  const port = Number(value);
  if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error(`Invalid port: ${value}`);
  return port;
}

async function main(): Promise<void> {
  try {
    const options = parseArgs(process.argv.slice(2));
    if (options.command === 'build') {
      const pages = await buildSite({ ...options, onStats: (stats) => console.log(`Pages built: ${stats.pagesBuilt}, skipped: ${stats.pagesSkipped}, time saved: ${stats.timeSavedMs}ms.`) });
      console.log(`Built ${pages.length} page${pages.length === 1 ? '' : 's'}.`);
    } else if (options.command === 'serve') {
      const server = await startDevServer(options);
      console.log(`Development server running at http://localhost:${server.port}`);
    } else throw new Error(usage());
  } catch (error) {
    console.error(error instanceof Error ? error.message : error);
    process.exitCode = 1;
  }
}

if (require.main === module) void main();
