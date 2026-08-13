#!/usr/bin/env node
import { buildSite } from './generator';

function parseArguments(args: string[]): { contentDir?: string; outputDir?: string; templateDir?: string } {
  const options: { contentDir?: string; outputDir?: string; templateDir?: string } = {};
  for (let index = 0; index < args.length; index += 1) {
    const argument = args[index];
    if (argument === '--content') options.contentDir = args[++index];
    else if (argument === '--output') options.outputDir = args[++index];
    else if (argument === '--templates') options.templateDir = args[++index];
    else if (argument !== 'build') throw new Error(`Unknown argument: ${argument}`);
  }
  return options;
}

async function main(): Promise<void> {
  const args = process.argv.slice(2);
  if (args[0] !== 'build') throw new Error('Usage: ssg build [--content <dir>] [--output <dir>] [--templates <dir>]');
  const pages = await buildSite(parseArguments(args));
  console.log(`Generated ${pages.length} page(s).`);
}

main().catch((error: unknown) => {
  console.error(error instanceof Error ? error.message : error);
  process.exitCode = 1;
});
