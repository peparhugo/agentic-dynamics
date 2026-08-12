#!/usr/bin/env node
import { buildSite } from './site-generator';

function usage(): void {
  console.error('Usage: ssg build [--content <dir>] [--output <dir>] [--templates <dir>]');
}

function parseOptions(args: string[]): { contentDir?: string; outputDir?: string; templatesDir?: string } {
  const options: { contentDir?: string; outputDir?: string; templatesDir?: string } = {};
  for (let index = 0; index < args.length; index += 1) {
    const option = args[index];
    if (option !== '--content' && option !== '--output' && option !== '--templates') {
      throw new Error(`Unknown option: ${option}`);
    }
    const value = args[++index];
    if (!value || value.startsWith('--')) throw new Error(`${option} requires a directory`);
    if (option === '--content') options.contentDir = value;
    else if (option === '--output') options.outputDir = value;
    else options.templatesDir = value;
  }
  return options;
}

async function main(): Promise<void> {
  const [command, ...args] = process.argv.slice(2);
  if (command !== 'build') {
    usage();
    process.exitCode = 1;
    return;
  }
  try {
    const result = await buildSite(parseOptions(args));
    console.log(`Built ${result.pages.length} page${result.pages.length === 1 ? '' : 's'}.`);
  } catch (error) {
    console.error(error instanceof Error ? error.message : error);
    process.exitCode = 1;
  }
}

void main();
