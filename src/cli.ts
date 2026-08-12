#!/usr/bin/env node
import { buildSite } from './generator';

function usage(): string {
  return 'Usage: ssg build [--content <dir>] [--output <dir>]';
}

export function parseArgs(args: string[]): { command: string; contentDir?: string; outputDir?: string } {
  const [command, ...flags] = args;
  const options: { command: string; contentDir?: string; outputDir?: string } = { command: command || '' };
  for (let index = 0; index < flags.length; index += 1) {
    const flag = flags[index];
    if (flag === '--content' || flag === '--output') {
      const value = flags[++index];
      if (!value) throw new Error(`${flag} requires a directory`);
      if (flag === '--content') options.contentDir = value;
      else options.outputDir = value;
    } else if (flag.startsWith('--content=')) options.contentDir = flag.slice('--content='.length);
    else if (flag.startsWith('--output=')) options.outputDir = flag.slice('--output='.length);
    else throw new Error(`Unknown option: ${flag}`);
  }
  return options;
}

async function main(): Promise<void> {
  try {
    const options = parseArgs(process.argv.slice(2));
    if (options.command !== 'build') throw new Error(usage());
    const pages = await buildSite(options);
    console.log(`Built ${pages.length} page${pages.length === 1 ? '' : 's'}.`);
  } catch (error) {
    console.error(error instanceof Error ? error.message : error);
    process.exitCode = 1;
  }
}

if (require.main === module) void main();
