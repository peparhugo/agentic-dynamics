#!/usr/bin/env node
import { buildSite } from './generator.js';

function usage(): string {
  return 'Usage: ssg build [--content <dir>] [--output <dir>]';
}

export function parseArguments(args: string[]): { contentDir?: string; outputDir?: string } {
  if (args[0] !== 'build') throw new Error(usage());
  const options: { contentDir?: string; outputDir?: string } = {};
  for (let index = 1; index < args.length; index += 1) {
    const flag = args[index];
    const value = args[index + 1];
    if ((flag !== '--content' && flag !== '--output') || !value || value.startsWith('--')) throw new Error(usage());
    if (flag === '--content') options.contentDir = value;
    if (flag === '--output') options.outputDir = value;
    index += 1;
  }
  return options;
}

async function main(): Promise<void> {
  try {
    const options = parseArguments(process.argv.slice(2));
    const pages = await buildSite(options);
    process.stdout.write(`Generated ${pages.length} page(s).\n`);
  } catch (error) {
    process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
    process.exitCode = 1;
  }
}

void main();
