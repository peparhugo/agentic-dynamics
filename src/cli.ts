#!/usr/bin/env node
import { buildSite, BuildOptions } from './generator';

export function parseArgs(args: string[]): BuildOptions {
  const options: BuildOptions = {};
  for (let index = 0; index < args.length; index += 1) {
    const argument = args[index];
    if (argument === '--content' || argument === '--output') {
      const value = args[++index];
      if (!value) throw new Error(`${argument} requires a directory`);
      if (argument === '--content') options.contentDir = value;
      else options.outputDir = value;
    }
  }
  return options;
}

if (require.main === module) {
  const [command, ...args] = process.argv.slice(2);
  if (command !== 'build') {
    console.error('Usage: ssg build [--content <dir>] [--output <dir>]');
    process.exitCode = 1;
  } else {
    try {
      const pages = buildSite(parseArgs(args));
      console.log(`Generated ${pages.length} page${pages.length === 1 ? '' : 's'} .`);
    } catch (error) {
      console.error(error instanceof Error ? error.message : error);
      process.exitCode = 1;
    }
  }
}
