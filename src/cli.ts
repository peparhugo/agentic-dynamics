#!/usr/bin/env node
import { buildSite } from './build';

function option(args: string[], name: string): string | undefined {
  const index = args.indexOf(name);
  if (index === -1) return undefined;
  const value = args[index + 1];
  if (!value || value.startsWith('--')) throw new Error(`${name} requires a directory`);
  return value;
}

async function main(): Promise<void> {
  const args = process.argv.slice(2);
  if (args[0] !== 'build') throw new Error('Usage: ssg build [--content <dir>] [--output <dir>]');
  const pages = await buildSite(option(args, '--content'), option(args, '--output'));
  process.stdout.write(`Generated ${pages.length} page(s).\n`);
}

main().catch((error: unknown) => {
  process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
  process.exitCode = 1;
});
