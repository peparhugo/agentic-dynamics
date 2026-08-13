#!/usr/bin/env node

import { buildSite } from './index.js';

interface CliOptions {
  contentDir?: string;
  outputDir?: string;
}

function usage(): string {
  return 'Usage: ssg build [--content <dir>] [--output <dir>]';
}

function parseOptions(args: string[]): CliOptions {
  const options: CliOptions = {};
  for (let index = 0; index < args.length; index += 1) {
    const option = args[index];
    const value = args[index + 1];
    if ((option === '--content' || option === '--output') && (!value || value.startsWith('--'))) {
      throw new Error(`${option} requires a directory`);
    }
    if (option === '--content') {
      options.contentDir = value;
      index += 1;
    } else if (option === '--output') {
      options.outputDir = value;
      index += 1;
    } else {
      throw new Error(`Unknown option: ${option}`);
    }
  }
  return options;
}

export async function run(args: string[]): Promise<void> {
  if (args[0] !== 'build') {
    throw new Error(usage());
  }
  const options = parseOptions(args.slice(1));
  const pages = await buildSite(options);
  process.stdout.write(`Generated ${pages.length} page${pages.length === 1 ? '' : 's'}.\n`);
}

if (require.main === module) {
  run(process.argv.slice(2)).catch((error: unknown) => {
    process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
    process.exitCode = 1;
  });
}
