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

function parseOptions(args: string[]): CliOptions {
  const options: CliOptions = {};
  for (let index = 0; index < args.length; index += 1) {
    const option = args[index];
    if (option !== '--content' && option !== '--output' && option !== '--templates') {
      throw new Error(`Unknown option: ${option}`);
    }
    const value = args[index + 1];
    if (!value || value.startsWith('--')) throw new Error(`Missing value for ${option}`);
    if (option === '--content') options.contentDir = value;
    if (option === '--output') options.outputDir = value;
    if (option === '--templates') options.templatesDir = value;
    index += 1;
  }
  return options;
}

export async function run(args: string[]): Promise<void> {
  const [command, ...optionArgs] = args;
  if (command !== 'build') throw new Error(usage());
  const pages = await buildSite(parseOptions(optionArgs));
  process.stdout.write(`Generated ${pages.length} page${pages.length === 1 ? '' : 's'}.\n`);
}

if (require.main === module) {
  run(process.argv.slice(2)).catch((error: unknown) => {
    const message = error instanceof Error ? error.message : String(error);
    process.stderr.write(`Error: ${message}\n`);
    process.exitCode = 1;
  });
}
