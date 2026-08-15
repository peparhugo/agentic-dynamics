#!/usr/bin/env node
import { build } from './build';

interface ParsedArgs {
  command?: string;
  content: string;
  output: string;
}

function parseArgs(argv: string[]): ParsedArgs {
  const result: ParsedArgs = { command: argv[0], content: './content', output: './dist' };
  for (let i = 1; i < argv.length; i++) {
    const arg = argv[i];
    if (arg === '--content') {
      result.content = argv[++i] ?? result.content;
    } else if (arg === '--output') {
      result.output = argv[++i] ?? result.output;
    }
  }
  return result;
}

async function main(): Promise<void> {
  const args = parseArgs(process.argv.slice(2));

  if (args.command !== 'build') {
    console.error('Usage: ssg build [--content <dir>] [--output <dir>]');
    process.exit(1);
  }

  const pages = await build({ content: args.content, output: args.output });
  console.log(`Built ${pages.length} page(s) into ${args.output}.`);
}

main().catch((err) => {
  console.error(err instanceof Error ? err.message : err);
  process.exit(1);
});
