#!/usr/bin/env node
import { buildSite, BuildOptions } from './generator';

function usage(): string {
  return 'Usage: ssg build [--content <dir>] [--output <dir>]';
}

export function parseArguments(args: string[]): BuildOptions {
  const options: BuildOptions = {};
  for (let index = 0; index < args.length; index += 1) {
    const argument = args[index];
    if (argument === '--content' || argument === '--output') {
      const value = args[++index];
      if (!value || value.startsWith('--')) throw new Error(`${argument} requires a directory`);
      if (argument === '--content') options.contentDir = value;
      else options.outputDir = value;
    } else {
      throw new Error(`Unknown option: ${argument}`);
    }
  }
  return options;
}

export async function run(args: string[]): Promise<void> {
  if (args[0] !== 'build') throw new Error(usage());
  const pages = await buildSite(parseArguments(args.slice(1)));
  process.stdout.write(`Generated ${pages.length} page(s).\n`);
}

if (require.main === module) {
  run(process.argv.slice(2)).catch((error: unknown) => {
    process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
    process.exitCode = 1;
  });
}
