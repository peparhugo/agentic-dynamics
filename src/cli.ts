#!/usr/bin/env node
import { buildSite } from './generator';

function usage(): string {
  return 'Usage: ssg build [--content <dir>] [--output <dir>] [--templates <dir>]';
}

function options(args: string[]): { contentDir?: string; outputDir?: string; templateDir?: string } {
  const result: { contentDir?: string; outputDir?: string; templateDir?: string } = {};
  for (let index = 0; index < args.length; index += 1) {
    const value = args[index + 1];
    if ((args[index] === '--content' || args[index] === '--output' || args[index] === '--templates') && (!value || value.startsWith('--'))) throw new Error(`Missing value for ${args[index]}`);
    if (args[index] === '--content') result.contentDir = value;
    if (args[index] === '--output') result.outputDir = value;
    if (args[index] === '--templates') result.templateDir = value;
    if (args[index].startsWith('--') && args[index] !== '--content' && args[index] !== '--output' && args[index] !== '--templates') throw new Error(`Unknown option: ${args[index]}`);
  }
  return result;
}

async function main(): Promise<void> {
  const [command, ...args] = process.argv.slice(2);
  if (command !== 'build') throw new Error(usage());
  const pages = await buildSite(options(args));
  console.log(`Generated ${pages.length} page(s).`);
}

main().catch((error: unknown) => {
  console.error(error instanceof Error ? error.message : error);
  process.exitCode = 1;
});
