#!/usr/bin/env node
import { buildSite, BuildOptions } from './index';

function usage(): string {
  return 'Usage: ssg build [--content <dir>] [--output <dir>] [--templates <dir>]';
}

export function parseArgs(args: string[]): BuildOptions {
  const options: BuildOptions = {};
  for (let index = 0; index < args.length; index += 1) {
    const argument = args[index];
    if (argument === '--content' || argument === '--output' || argument === '--templates') {
      const value = args[index + 1];
      if (!value || value.startsWith('--')) throw new Error(`${argument} requires a directory`);
      if (argument === '--content') options.contentDir = value;
      else if (argument === '--output') options.outputDir = value;
      else options.templatesDir = value;
      index += 1;
    } else if (argument.startsWith('--')) {
      throw new Error(`Unknown option: ${argument}`);
    } else {
      throw new Error(`Unexpected argument: ${argument}`);
    }
  }
  return options;
}

export function main(args: string[] = process.argv.slice(2)): void {
  const [command, ...rest] = args;
  if (command !== 'build') throw new Error(usage());
  buildSite(parseArgs(rest));
}

if (require.main === module) {
  try {
    main();
  } catch (error) {
    process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
    process.exitCode = 1;
  }
}
