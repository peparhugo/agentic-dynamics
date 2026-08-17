#!/usr/bin/env node
import { buildSite } from './generate';

export interface CliOptions {
  command: string | null;
  content: string;
  output: string;
  templates: string;
  help: boolean;
}

export function parseArgs(args: string[]): CliOptions {
  const options: CliOptions = {
    command: null,
    content: './content',
    output: './dist',
    templates: './templates',
    help: false,
  };

  for (let i = 0; i < args.length; i += 1) {
    const arg = args[i];
    if (arg === 'build') {
      options.command = 'build';
    } else if (arg === '--content' || arg === '-c') {
      options.content = args[i + 1] ?? options.content;
      if (args[i + 1] !== undefined) i += 1;
    } else if (arg.startsWith('--content=')) {
      options.content = arg.slice('--content='.length);
    } else if (arg === '--output' || arg === '-o') {
      options.output = args[i + 1] ?? options.output;
      if (args[i + 1] !== undefined) i += 1;
    } else if (arg.startsWith('--output=')) {
      options.output = arg.slice('--output='.length);
    } else if (arg === '--templates' || arg === '-t') {
      options.templates = args[i + 1] ?? options.templates;
      if (args[i + 1] !== undefined) i += 1;
    } else if (arg.startsWith('--templates=')) {
      options.templates = arg.slice('--templates='.length);
    } else if (arg === '--help' || arg === '-h') {
      options.help = true;
    }
  }

  return options;
}

export function printUsage(): string {
  return [
    'Usage: npx ssg build [options]',
    '',
    'Build a static site from Markdown files.',
    '',
    'Options:',
    '  --content <dir>, -c <dir>  Markdown content directory (default: ./content)',
    '  --output <dir>,  -o <dir>  Output directory (default: ./dist)',
    '  --templates <dir>, -t <dir> Template directory (default: ./templates)',
    '  --help, -h                 Show this help message',
  ].join('\n');
}

export async function run(argv: string[]): Promise<void> {
  const options = parseArgs(argv.slice(2));

  if (options.help || options.command !== 'build') {
    process.stdout.write(`${printUsage()}\n`);
    return;
  }

  const result = await buildSite(options.content, options.output, options.templates);
  process.stdout.write(`Built ${result.pages.length} page(s) into ${options.output}\n`);
}

if (require.main === module) {
  run(process.argv).catch((err: unknown) => {
    const message = err instanceof Error ? err.message : String(err);
    process.stderr.write(`${message}\n`);
    process.exitCode = 1;
  });
}
