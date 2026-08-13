#!/usr/bin/env node
import { buildSite } from './generator.js';

interface CliOptions {
  content?: string;
  output?: string;
}

export function parseArguments(args: string[]): CliOptions {
  const options: CliOptions = {};
  for (let index = 0; index < args.length; index += 1) {
    const argument = args[index];
    if (argument === '--content' || argument === '--output') {
      const value = args[index + 1];
      if (!value || value.startsWith('--')) throw new Error(`${argument} requires a directory`);
      options[argument.slice(2) as keyof CliOptions] = value;
      index += 1;
    } else {
      throw new Error(`Unknown option: ${argument}`);
    }
  }
  return options;
}

export async function run(args: string[]): Promise<void> {
  if (args[0] !== 'build') throw new Error('Usage: ssg build [--content <dir>] [--output <dir>]');
  const pages = await buildSite(parseArguments(args.slice(1)));
  process.stdout.write(`Generated ${pages.length} page${pages.length === 1 ? '' : 's'}.\n`);
}

if (/cli\.(?:js|ts)$/.test(process.argv[1] ?? '')) {
  run(process.argv.slice(2)).catch((error: unknown) => {
    process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
    process.exitCode = 1;
  });
}
