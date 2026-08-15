#!/usr/bin/env node
import { buildSite } from './generator';

function optionValue(args: string[], option: string): string | undefined {
  const index = args.indexOf(option);
  if (index === -1) return undefined;
  if (!args[index + 1] || args[index + 1].startsWith('--')) throw new Error(`${option} requires a directory`);
  return args[index + 1];
}

function main(args: string[]): void {
  if (args[0] !== 'build') throw new Error('Usage: ssg build [--content <dir>] [--output <dir>] [--templates <dir>]');
  const pages = buildSite({
    contentDir: optionValue(args, '--content'),
    outputDir: optionValue(args, '--output'),
    templatesDir: optionValue(args, '--templates'),
  });
  console.log(`Built ${pages.length} page${pages.length === 1 ? '' : 's'}.`);
}

try {
  main(process.argv.slice(2));
} catch (error) {
  console.error(error instanceof Error ? error.message : error);
  process.exitCode = 1;
}
