#!/usr/bin/env node
import { buildSite } from './generator';

function parseArgs(args: string[]): { contentDir: string; outputDir: string; templatesDir?: string } {
  if (args[0] !== 'build') throw new Error('Usage: ssg build [--content <dir>] [--output <dir>] [--templates <dir>]');
  let contentDir = './content';
  let outputDir = './dist';
  let templatesDir: string | undefined;
  for (let index = 1; index < args.length; index += 1) {
    const option = args[index];
    const value = args[index + 1];
    if ((option === '--content' || option === '--output' || option === '--templates') && value && !value.startsWith('--')) {
      if (option === '--content') contentDir = value;
      else if (option === '--output') outputDir = value;
      else templatesDir = value;
      index += 1;
    } else {
      throw new Error(`Unknown or incomplete option: ${option}`);
    }
  }
  return { contentDir, outputDir, templatesDir };
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
