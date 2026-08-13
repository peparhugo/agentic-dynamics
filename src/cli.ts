#!/usr/bin/env node
import { buildSite } from './generator.js';
import { parseBuildOptions } from './options.js';

function usage(): string {
  return 'Usage: ssg build [--content <dir>] [--output <dir>] [--templates <dir>]';
}

async function main(): Promise<void> {
  const [command, ...args] = process.argv.slice(2);
  if (command !== 'build') throw new Error(usage());
  const pages = await buildSite(parseBuildOptions(args));
  process.stdout.write(`Generated ${pages.length} page(s).\n`);
}

main().catch((error: unknown) => {
  process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
  process.exitCode = 1;
});
