import { build } from './generator';
import { BuildOptions } from './types';

const DEFAULT_CONTENT_DIR = 'content';
const DEFAULT_OUTPUT_DIR = 'dist';

export interface CliArgs {
  command: string;
  options: BuildOptions;
}

function usage(): string {
  return `Usage: ssg build [--content <dir>] [--output <dir>]

Build a static site from Markdown files.

Options:
  --content <dir>  Content directory containing Markdown files (default: ./content)
  --output <dir>   Output directory for generated HTML (default: ./dist)
  --help           Show this help message`;
}

export function parseArgs(argv: string[]): CliArgs {
  const options: BuildOptions = {
    contentDir: DEFAULT_CONTENT_DIR,
    outputDir: DEFAULT_OUTPUT_DIR,
  };
  let command = 'build';
  let seenPositional = false;

  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];

    if (arg === '--help' || arg === '-h') {
      throw new HelpError(usage());
    }

    const equalsIndex = arg.indexOf('=');
    const flag = equalsIndex === -1 ? arg : arg.slice(0, equalsIndex);
    const inlineValue = equalsIndex === -1 ? undefined : arg.slice(equalsIndex + 1);

    if (flag === '--content') {
      options.contentDir = inlineValue ?? argv[++i];
      if (!options.contentDir) {
        throw new Error('--content requires a directory argument');
      }
    } else if (flag === '--output') {
      options.outputDir = inlineValue ?? argv[++i];
      if (!options.outputDir) {
        throw new Error('--output requires a directory argument');
      }
    } else if (arg.startsWith('-')) {
      throw new Error(`unknown argument: ${arg}`);
    } else {
      if (seenPositional) {
        throw new Error(`unknown argument: ${arg}`);
      }
      seenPositional = true;
      command = arg;
    }
  }

  if (command !== 'build') {
    throw new Error(`unknown command: ${command}`);
  }

  return { command, options };
}

export class HelpError extends Error {}

export async function main(argv: string[]): Promise<void> {
  const { options } = parseArgs(argv);

  const pages = await build(options);
  process.stdout.write(
    `Built ${pages.length} page${pages.length === 1 ? '' : 's'} into ${options.outputDir}\n`
  );
}
