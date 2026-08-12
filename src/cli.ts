#!/usr/bin/env node
import { buildSite } from './build';
import { Page } from './page';

export interface CliOptions {
  content: string;
  output: string;
}

export interface ParsedCli {
  command: string;
  options: CliOptions;
}

const DEFAULT_CONTENT = './content';
const DEFAULT_OUTPUT = './dist';

function usage(): string {
  return [
    'Usage: ssg build [options]',
    '',
    'Options:',
    '  --content <dir>   Markdown source directory (default: ./content)',
    '  --output <dir>    Output directory (default: ./dist)',
    '  -h, --help        Show this help',
  ].join('\n');
}

function parseFlagValue(argv: string[], flag: string, index: number): string | null {
  const arg = argv[index];
  if (arg === flag) {
    const value = argv[index + 1];
    return value !== undefined ? value : null;
  }
  if (arg.startsWith(`${flag}=`)) {
    return arg.slice(flag.length + 1);
  }
  return null;
}

export function parseArgs(argv: string[]): ParsedCli | null {
  const args = argv.slice();
  const command = args.shift();
  if (command === undefined || command === '-h' || command === '--help') return null;
  if (command !== 'build') return null;

  const options: CliOptions = { content: DEFAULT_CONTENT, output: DEFAULT_OUTPUT };
  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    if (arg === '-h' || arg === '--help') return null;
    const contentValue = parseFlagValue(args, '--content', i);
    if (contentValue !== null) {
      options.content = contentValue;
      if (args[i] === '--content') i++;
      continue;
    }
    const outputValue = parseFlagValue(args, '--output', i);
    if (outputValue !== null) {
      options.output = outputValue;
      if (args[i] === '--output') i++;
      continue;
    }
    return null;
  }
  return { command, options };
}

export function run(argv: string[]): number {
  const parsed = parseArgs(argv);
  if (parsed === null) {
    process.stdout.write(usage() + '\n');
    return 1;
  }

  try {
    const pages: Page[] = buildSite(parsed.options.content, parsed.options.output);
    process.stdout.write(`Built ${pages.length} page(s) into ${parsed.options.output}\n`);
    return 0;
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    process.stderr.write(`Error: ${message}\n`);
    return 1;
  }
}

function main(): void {
  process.exitCode = run(process.argv.slice(2));
}

if (require.main === module) {
  main();
}
