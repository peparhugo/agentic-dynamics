#!/usr/bin/env node
import * as path from 'path';
import { build } from './ssg';

export interface CliOptions {
  contentDir: string;
  outputDir: string;
}

export type ParseResult = CliOptions | 'help' | 'invalid';

export function printHelp(): void {
  console.log(`Usage: ssg build [options]

Generate a static site from Markdown files.

Options:
  --content <dir>  Directory containing Markdown content (default: ./content)
  --output <dir>   Directory to write the generated HTML (default: ./dist)
  --help, -h       Show this help message
`);
}

export function parseArgs(args: string[]): ParseResult {
  if (args.length === 0) {
    return 'invalid';
  }
  const subcommand = args[0];
  if (subcommand === '--help' || subcommand === '-h') {
    return 'help';
  }
  if (subcommand !== 'build') {
    return 'invalid';
  }
  const options: CliOptions = { contentDir: 'content', outputDir: 'dist' };
  for (let i = 1; i < args.length; i++) {
    const arg = args[i];
    if (arg === '--help' || arg === '-h') {
      return 'help';
    }
    if (arg === '--content' || arg === '--output') {
      const value = args[i + 1];
      if (!value || value.startsWith('--')) {
        return 'invalid';
      }
      if (arg === '--content') {
        options.contentDir = value;
      } else {
        options.outputDir = value;
      }
      i += 1;
    } else {
      return 'invalid';
    }
  }
  return options;
}

async function main(): Promise<void> {
  const parsed = parseArgs(process.argv.slice(2));
  if (parsed === 'help') {
    printHelp();
    return;
  }
  if (parsed === 'invalid') {
    console.error('Invalid arguments. Run `ssg --help` for usage.');
    process.exitCode = 1;
    return;
  }
  try {
    const pages = await build(parsed);
    console.log(`Generated ${pages.length} page(s) in ${path.resolve(parsed.outputDir)}`);
  } catch (err) {
    console.error(`Build failed: ${(err as Error).message}`);
    process.exitCode = 1;
  }
}

if (require.main === module) {
  void main();
}
