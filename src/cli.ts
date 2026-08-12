import { resolve } from 'path';
import { buildSite } from './generator';
import type { BuildOptions } from './types';

export const DEFAULT_CONTENT_DIR = 'content';
export const DEFAULT_OUTPUT_DIR = 'dist';

export interface ParsedArgs {
  command: string;
  options: BuildOptions;
}

export function parseArgs(argv: string[]): ParsedArgs {
  const options: BuildOptions = {
    contentDir: resolve(process.cwd(), DEFAULT_CONTENT_DIR),
    outputDir: resolve(process.cwd(), DEFAULT_OUTPUT_DIR)
  };

  let command = 'build';
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    if (arg === '--content' || arg === '-c') {
      options.contentDir = resolve(process.cwd(), argv[++i]);
    } else if (arg === '--output' || arg === '-o') {
      options.outputDir = resolve(process.cwd(), argv[++i]);
    } else if (arg.startsWith('--content=')) {
      options.contentDir = resolve(process.cwd(), arg.slice('--content='.length));
    } else if (arg.startsWith('--output=')) {
      options.outputDir = resolve(process.cwd(), arg.slice('--output='.length));
    } else if (!arg.startsWith('-')) {
      command = arg;
    } else if (arg === '--help' || arg === '-h') {
      command = 'help';
    }
  }
  return { command, options };
}

export function printHelp(): string {
  return [
    'ssg - a static site generator',
    '',
    'Usage:',
    '  npx ssg build [options]',
    '',
    'Options:',
    '  --content <dir>    Markdown content directory (default: ./content)',
    '  --output <dir>     Output directory (default: ./dist)',
    '  -h, --help         Show this help message'
  ].join('\n');
}

export async function run(argv: string[]): Promise<void> {
  const { command, options } = parseArgs(argv);

  if (command === 'help') {
    process.stdout.write(printHelp() + '\n');
    return;
  }

  if (command !== 'build') {
    throw new Error(`Unknown command: ${command}`);
  }

  const pages = await buildSite(options);
  process.stdout.write(`Built ${pages.length} page(s) from ${options.contentDir} into ${options.outputDir}\n`);
}

if (require.main === module) {
  run(process.argv.slice(2)).catch((error: Error) => {
    process.stderr.write(`Error: ${error.message}\n`);
    process.exit(1);
  });
}
