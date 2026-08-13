#!/usr/bin/env node
import { buildSite } from './site.js';

function usage(): string {
  return 'Usage: ssg build [--content <dir>] [--output <dir>]';
}

function parseArguments(arguments_: string[]): { contentDir?: string; outputDir?: string } {
  const options: { contentDir?: string; outputDir?: string } = {};
  for (let index = 0; index < arguments_.length; index += 1) {
    const argument = arguments_[index];
    if (argument === '--content' || argument === '--output') {
      const value = arguments_[index + 1];
      if (!value || value.startsWith('--')) throw new Error(`Missing value for ${argument}`);
      if (argument === '--content') options.contentDir = value;
      else options.outputDir = value;
      index += 1;
    } else {
      throw new Error(`Unknown option: ${argument}`);
    }
  }
  return options;
}

async function main(): Promise<void> {
  const [command, ...arguments_] = process.argv.slice(2);
  if (command !== 'build') throw new Error(usage());
  const pages = await buildSite(parseArguments(arguments_));
  process.stdout.write(`Built ${pages.length} page(s).\n`);
}

main().catch((error: unknown) => {
  process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
  process.exitCode = 1;
});
