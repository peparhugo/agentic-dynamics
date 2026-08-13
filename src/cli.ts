#!/usr/bin/env node
import { buildSite, BuildOptions } from './generator';

export function parseArgs(args: string[]): BuildOptions {
  if (args[0] !== 'build') {
    throw new Error('Usage: ssg build [--content <dir>] [--output <dir>] [--templates <dir>]');
  }

  const options: BuildOptions = {};
  for (let index = 1; index < args.length; index += 1) {
    const option = args[index];
    const value = args[index + 1];
    if ((option === '--content' || option === '--output' || option === '--templates') && value && !value.startsWith('--')) {
      if (option === '--content') options.contentDir = value;
      if (option === '--output') options.outputDir = value;
      if (option === '--templates') options.templatesDir = value;
      index += 1;
      continue;
    }
    throw new Error(`Invalid option: ${option}`);
  }
  return options;
}

export async function run(args: string[]): Promise<void> {
  const options = parseArgs(args);
  const pages = await buildSite(options);
  process.stdout.write(`Built ${pages.length} page${pages.length === 1 ? '' : 's'}.\n`);
}

if (require.main === module) {
  run(process.argv.slice(2)).catch((error: unknown) => {
    const message = error instanceof Error ? error.message : String(error);
    process.stderr.write(`Error: ${message}\n`);
    process.exitCode = 1;
  });
}
