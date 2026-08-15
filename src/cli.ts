#!/usr/bin/env node
import { buildSite } from './generator';

const DEFAULT_CONTENT_DIR = './content';
const DEFAULT_OUTPUT_DIR = './dist';

export interface CliOptions {
  command: string;
  contentDir: string;
  outputDir: string;
}

export function parseArgs(argv: string[]): CliOptions {
  const opts: CliOptions = {
    command: '',
    contentDir: DEFAULT_CONTENT_DIR,
    outputDir: DEFAULT_OUTPUT_DIR,
  };
  const args = argv.slice();
  if (args.length === 0) {
    return opts;
  }
  if (args.includes('--help') || args.includes('-h')) {
    opts.command = 'help';
    return opts;
  }
  opts.command = args[0] ?? '';
  for (let i = 1; i < args.length; i++) {
    const arg = args[i];
    if (arg === '--content') {
      opts.contentDir = args[i + 1] ?? DEFAULT_CONTENT_DIR;
      i += 1;
    } else if (arg === '--output') {
      opts.outputDir = args[i + 1] ?? DEFAULT_OUTPUT_DIR;
      i += 1;
    }
  }
  return opts;
}

export function printHelp(): void {
  console.log(
    [
      'Static Site Generator',
      '',
      'Usage:',
      '  npx ssg build [options]',
      '',
      'Options:',
      '  --content <dir>   Markdown content directory (default: ./content)',
      '  --output <dir>    Output directory (default: ./dist)',
      '  -h, --help        Show this help',
      '',
    ].join('\n')
  );
}

export function main(argv: string[]): number {
  const opts = parseArgs(argv);

  if (opts.command === 'help') {
    printHelp();
    return 0;
  }
  if (opts.command !== 'build') {
    console.error(`Unknown command: "${opts.command}". Run "npx ssg build".`);
    return 1;
  }

  try {
    const pages = buildSite({ contentDir: opts.contentDir, outputDir: opts.outputDir });
    console.log(`Built ${pages.length} page${pages.length === 1 ? '' : 's'} into ${opts.outputDir}`);
    return 0;
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    console.error(`Build failed: ${message}`);
    return 1;
  }
}

if (require.main === module) {
  process.exitCode = main(process.argv.slice(2));
}
