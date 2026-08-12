#!/usr/bin/env node

import { buildSite } from './build';

const DEFAULT_CONTENT = './content';
const DEFAULT_OUTPUT = './dist';

export interface CliOptions {
  contentDir: string;
  outputDir: string;
}

export interface ParseArgsResult {
  command?: string;
  options: CliOptions;
  error?: string;
}

export function parseArgs(args: string[]): ParseArgsResult {
  const options: CliOptions = {
    contentDir: DEFAULT_CONTENT,
    outputDir: DEFAULT_OUTPUT,
  };

  const command = args.find((a) => a === 'build' || a === 'serve');

  let i = 0;
  while (i < args.length) {
    const arg = args[i];
    if (arg === '--content' || arg === '--output') {
      const value = args[i + 1];
      if (value === undefined) {
        return { command, options, error: `Missing value for ${arg}` };
      }
      if (arg === '--content') {
        options.contentDir = value;
      } else {
        options.outputDir = value;
      }
      i += 2;
    } else {
      i += 1;
    }
  }

  return { command, options };
}

export function run(args: string[]): void {
  const { command, options, error } = parseArgs(args);

  if (error) {
    console.error(`Error: ${error}`);
    process.exitCode = 1;
    return;
  }

  if (command !== 'build') {
    console.error('Usage: ssg build [--content <dir>] [--output <dir>]');
    process.exitCode = 1;
    return;
  }

  const result = buildSite(options.contentDir, options.outputDir);
  console.log(`Built ${result.pages.length} page(s) into ${options.outputDir}`);
}

if (require.main === module) {
  run(process.argv.slice(2));
}
