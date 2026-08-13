#!/usr/bin/env node
import { buildSite } from './site';

function usage(): string {
  return 'Usage: ssg build [--content <dir>] [--output <dir>] [--templates <dir>]';
}

function parseArguments(args: string[]): { contentDir?: string; outputDir?: string; templatesDir?: string } {
  const options: { contentDir?: string; outputDir?: string; templatesDir?: string } = {};
  for (let index = 0; index < args.length; index += 1) {
    const argument = args[index];
    if (argument !== '--content' && argument !== '--output' && argument !== '--templates') throw new Error(`Unknown option: ${argument}`);
    const value = args[index + 1];
    if (!value || value.startsWith('--')) throw new Error(`Missing value for ${argument}`);
    if (argument === '--content') options.contentDir = value;
    else if (argument === '--output') options.outputDir = value;
    else options.templatesDir = value;
    index += 1;
  }
  return options;
}

function main(): void {
  const [command, ...args] = process.argv.slice(2);
  if (command !== 'build') throw new Error(usage());
  const pages = buildSite(parseArguments(args));
  process.stdout.write(`Generated ${pages.length} page(s).\n`);
}

try {
  main();
} catch (error) {
  process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
  process.exitCode = 1;
}
