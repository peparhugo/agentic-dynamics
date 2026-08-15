#!/usr/bin/env node
import { buildSite } from './index';

interface CliOptions {
  contentDir?: string;
  outputDir?: string;
  templatesDir?: string;
}

function usage(): string {
  return 'Usage: ssg build [--content <dir>] [--output <dir>] [--templates <dir>]';
}

export function parseArguments(args: string[]): CliOptions {
  if (args[0] !== 'build') throw new Error(usage());
  const options: CliOptions = {};

  for (let index = 1; index < args.length; index += 1) {
    const option = args[index];
    const value = args[index + 1];
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
  const pages = await buildSite(options);
  process.stdout.write(`Generated ${pages.length} page${pages.length === 1 ? '' : 's'}.\n`);
}

if (require.main === module) {
  run().catch((error: unknown) => {
    const message = error instanceof Error ? error.message : String(error);
    process.stderr.write(`Error: ${message}\n`);
    process.exitCode = 1;
  });
}
