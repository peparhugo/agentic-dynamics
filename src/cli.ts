#!/usr/bin/env node
import { SSGEngine } from './index';
import { startDevServer } from './server';

interface CliOptions {
  contentDir?: string;
  outputDir?: string;
  templatesDir?: string;
  port?: number;
  incremental?: boolean;
  clean?: boolean;
}

function usage(): string {
  return `Usage:
  ssg build [--incremental] [--clean] [--content <dir>] [--output <dir>] [--templates <dir>]
  ssg serve [--port <number>] [--content <dir>] [--output <dir>] [--templates <dir>]`;
}

export function parseArguments(args: string[]): CliOptions {
  const command = args[0];
  if (command !== 'build' && command !== 'serve') throw new Error(usage());
  const options: CliOptions = {};

  for (let index = 1; index < args.length; index += 1) {
    const option = args[index];
    const value = args[index + 1];
    if ((option === '--incremental' || option === '--clean') && command === 'build') {
      if (option === '--incremental') options.incremental = true;
      else options.clean = true;
      continue;
    }
    if (option === '--port' && command === 'serve' && value && !value.startsWith('--')) {
      const port = Number(value);
      if (!Number.isInteger(port) || port < 1 || port > 65535) {
        throw new Error(`Invalid port: ${value}\n${usage()}`);
      }
      options.port = port;
      index += 1;
      continue;
    }
    if ((option === '--content' || option === '--output' || option === '--templates') && value && !value.startsWith('--')) {
      if (option === '--content') options.contentDir = value;
      else if (option === '--output') options.outputDir = value;
      else options.templatesDir = value;
      index += 1;
      continue;
    }
    throw new Error(`Unknown or incomplete option: ${option}\n${usage()}`);
  }
  return options;
}

export async function run(args = process.argv.slice(2)): Promise<void> {
  const options = parseArguments(args);
  if (args[0] === 'serve') {
    await startDevServer(options);
    return;
  }
  const engine = new SSGEngine(options);
  const pages = await engine.build();
  const { pagesBuilt, pagesSkipped, timeSaved, duration } = engine.stats;
  process.stdout.write(`Generated ${pages.length} page${pages.length === 1 ? '' : 's'}. `
    + `Built ${pagesBuilt}, skipped ${pagesSkipped}, time saved ${timeSaved}ms (${duration}ms total).\n`);
}

if (require.main === module) {
  run().catch((error: unknown) => {
    const message = error instanceof Error ? error.message : String(error);
    process.stderr.write(`Error: ${message}\n`);
    process.exitCode = 1;
  });
}
