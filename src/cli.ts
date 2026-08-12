#!/usr/bin/env node
import { buildSite } from './index';

function argumentValue(args: string[], option: string): string | undefined {
  const index = args.indexOf(option);
  return index === -1 ? undefined : args[index + 1];
}

async function main(): Promise<void> {
  const args = process.argv.slice(2);
  if (args[0] !== 'build') {
    throw new Error('Usage: ssg build [--content <dir>] [--output <dir>]');
  }
  const content = argumentValue(args, '--content');
  const output = argumentValue(args, '--output');
  if (content === undefined && args.includes('--content') || output === undefined && args.includes('--output')) {
    throw new Error('Options --content and --output require a directory');
  }
  const pages = await buildSite({ contentDir: content, outputDir: output });
  process.stdout.write(`Built ${pages.length} page${pages.length === 1 ? '' : 's'}.\n`);
}

main().catch((error: unknown) => {
  process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
  process.exitCode = 1;
});
