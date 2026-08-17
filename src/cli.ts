#!/usr/bin/env node

import { buildSite } from './index';

interface CliOptions {
  content?: string;
  output?: string;
}

function printHelp(): void {
  console.log(`Usage: npx ssg build [options]

Generate a static site from Markdown files.

Options:
  --content <dir>   Content directory containing Markdown files (default: ./content)
  --output <dir>    Output directory for generated HTML (default: ./dist)
  -h, --help        Show this help message
`);
}

function parseArgs(args: string[]): CliOptions | null {
  const options: CliOptions = {};
  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    if (arg === '-h' || arg === '--help') {
      return null;
    }
    if (arg === '--content' || arg === '--output') {
      const value = args[i + 1];
      if (value === undefined || value.startsWith('--')) {
        console.error(`Error: option ${arg} requires a value`);
        process.exit(2);
      }
      if (arg === '--content') options.content = value;
      else options.output = value;
      i++;
      continue;
    }
    if (arg.startsWith('--content=')) {
      options.content = arg.slice('--content='.length);
      continue;
    }
    if (arg.startsWith('--output=')) {
      options.output = arg.slice('--output='.length);
      continue;
    }
    console.error(`Error: unknown option ${arg}`);
    process.exit(2);
  }
  return options;
}

function main(): void {
  const args = process.argv.slice(2);
  const command = args[0];

  if (!command || command === '-h' || command === '--help' || command === 'help') {
    printHelp();
    process.exit(0);
  }

  if (command !== 'build') {
    console.error(`Error: unknown command "${command}"`);
    printHelp();
    process.exit(1);
  }

  const options = parseArgs(args.slice(1));
  if (options === null) {
    printHelp();
    process.exit(0);
  }

  const site = buildSite({
    contentDir: options.content ?? 'content',
    outputDir: options.output ?? 'dist',
  });

  console.log(`Generated ${site.pages.length} page(s) in ${site.outputDir}`);
}

main();
