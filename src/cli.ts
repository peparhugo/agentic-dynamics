#!/usr/bin/env node
import { buildSite } from './site-generator';
import { startDevServer } from './dev-server';

function usage(): void {
  console.error('Usage: ssg build [--incremental] [--clean] [--content <dir>] [--output <dir>] [--templates <dir>]');
  console.error('       ssg serve [--content <dir>] [--output <dir>] [--templates <dir>] [--port <number>]');
}

interface CliOptions {
  contentDir?: string;
  outputDir?: string;
  templatesDir?: string;
  port?: number;
  incremental?: boolean;
  clean?: boolean;
}

function parseOptions(args: string[], allowPort = false): CliOptions {
  const options: CliOptions = {};
  for (let index = 0; index < args.length; index += 1) {
    const option = args[index];
    if (option === '--incremental') { options.incremental = true; continue; }
    if (option === '--clean') { options.clean = true; continue; }
    if (option !== '--content' && option !== '--output' && option !== '--templates' && (!allowPort || option !== '--port')) {
      throw new Error(`Unknown option: ${option}`);
    }
    const value = args[++index];
    if (!value || value.startsWith('--')) throw new Error(`${option} requires a value`);
    if (option === '--content') options.contentDir = value;
    else if (option === '--output') options.outputDir = value;
    else if (option === '--templates') options.templatesDir = value;
    else {
      const port = Number(value);
      if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error('--port must be between 1 and 65535');
      options.port = port;
    }
  }
  return options;
}

async function main(): Promise<void> {
  const [command, ...args] = process.argv.slice(2);
  if (command !== 'build' && command !== 'serve') {
    usage();
    process.exitCode = 1;
    return;
  }
  try {
    if (command === 'build') {
      const result = await buildSite(parseOptions(args));
      console.log(`Built ${result.stats.pagesBuilt} page${result.stats.pagesBuilt === 1 ? '' : 's'}, skipped ${result.stats.pagesSkipped}; saved ${result.stats.timeSaved}ms.`);
    } else {
      await startDevServer(parseOptions(args, true));
    }
  } catch (error) {
    console.error(error instanceof Error ? error.message : error);
    process.exitCode = 1;
  }
}

void main();
