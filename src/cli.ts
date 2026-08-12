#!/usr/bin/env node
import { buildSite } from './generator';

function usage(): string {
  return 'Usage: ssg build [--content <dir>] [--output <dir>] [--templates <dir>]';
}

function parseOptions(args: string[]): { contentDir?: string; outputDir?: string; templatesDir?: string } {
  const options: { contentDir?: string; outputDir?: string; templatesDir?: string } = {};
  for (let index = 0; index < args.length; index += 1) {
    const flag = args[index];
    if (flag !== '--content' && flag !== '--output' && flag !== '--templates') {
      throw new Error(`Unknown option: ${flag}`);
    }
    const value = args[index + 1];
    if (!value || value.startsWith('--')) {
      throw new Error(`Missing value for ${flag}`);
    }
    if (flag === '--content') options.contentDir = value;
    else if (flag === '--output') options.outputDir = value;
    else options.templatesDir = value;
    index += 1;
  }
  return options;
}

export async function run(args: string[]): Promise<void> {
  const [command, ...rest] = args;
  if (command !== 'build') throw new Error(usage());
  const pages = await buildSite(parseOptions(rest));
  console.log(`Built ${pages.length} page${pages.length === 1 ? '' : 's'}.`);
}

if (require.main === module) {
  run(process.argv.slice(2)).catch((error: unknown) => {
    console.error(error instanceof Error ? error.message : error);
    process.exitCode = 1;
  });
}
