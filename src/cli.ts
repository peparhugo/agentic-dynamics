#!/usr/bin/env node
import { buildSite } from './generator';

function parseArgs(args: string[]): { contentDir: string; outputDir: string } {
  if (args[0] !== 'build') throw new Error('Usage: ssg build [--content <dir>] [--output <dir>]');
  let contentDir = './content';
  let outputDir = './dist';
  for (let index = 1; index < args.length; index += 1) {
    const option = args[index];
    const value = args[index + 1];
    if ((option === '--content' || option === '--output') && value && !value.startsWith('--')) {
      if (option === '--content') contentDir = value;
      else outputDir = value;
      index += 1;
    } else {
      throw new Error(`Unknown or incomplete option: ${option}`);
    }
  }
  return { contentDir, outputDir };
}

export async function run(args: string[] = process.argv.slice(2)): Promise<void> {
  const options = parseArgs(args);
  const pages = await buildSite(options);
  process.stdout.write(`Built ${pages.length} page${pages.length === 1 ? '' : 's'}\n`);
}

if (require.main === module) {
  run().catch((error: unknown) => {
    process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
    process.exitCode = 1;
  });
}
