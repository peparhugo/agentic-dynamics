#!/usr/bin/env node
import { buildSite } from './site';

function usage(): string {
  return 'Usage: ssg build [--content <dir>] [--output <dir>]';
}

function parseArguments(args: string[]): { contentDir?: string; outputDir?: string } {
  const options: { contentDir?: string; outputDir?: string } = {};
  for (let index = 0; index < args.length; index += 1) {
    const argument = args[index];
    if (argument === '--content' || argument === '--output') {
      const value = args[index + 1];
      if (!value) throw new Error(`Missing value for ${argument}`);
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
  const [command, ...args] = process.argv.slice(2);
  if (command !== 'build') throw new Error(usage());
  const pages = await buildSite(parseArguments(args));
  process.stdout.write(`Built ${pages.length} page(s).\n`);
}

main().catch((error: unknown) => {
  process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
  process.exitCode = 1;
});
