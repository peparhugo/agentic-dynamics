#!/usr/bin/env node
import { buildSite } from './index.js';

interface CliOptions {
  command?: string;
  contentDir?: string;
  outputDir?: string;
  templatesDir?: string;
}

function usage(): string {
  return 'Usage: ssg build [--content <dir>] [--output <dir>] [--templates <dir>]';
}

export function parseArgs(args: string[]): CliOptions {
  const options: CliOptions = { command: args[0] };
  for (let index = 1; index < args.length; index += 1) {
    const argument = args[index];
    if (argument !== '--content' && argument !== '--output' && argument !== '--templates') {
      throw new Error(`Unknown option: ${argument}`);
    }
    const value = args[index + 1];
    if (!value || value.startsWith('--')) {
      throw new Error(`Missing value for ${argument}`);
    }
    if (argument === '--content') options.contentDir = value;
    if (argument === '--output') options.outputDir = value;
    if (argument === '--templates') options.templatesDir = value;
    index += 1;
  }
  return options;
}

export async function run(args: string[]): Promise<void> {
  const options = parseArgs(args);
  if (options.command !== 'build') throw new Error(usage());
  const pages = await buildSite(options);
  process.stdout.write(`Generated ${pages.length} page${pages.length === 1 ? '' : 's'}.\n`);
}

if (require.main === module) {
  run(process.argv.slice(2)).catch((error: unknown) => {
    process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
    process.exitCode = 1;
  });
}
