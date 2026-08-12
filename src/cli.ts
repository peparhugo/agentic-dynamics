import path from 'path';
import { buildSite } from './build';
import { BuildOptions } from './types';

const DEFAULT_CONTENT_DIR = './content';
const DEFAULT_OUTPUT_DIR = './dist';

export interface CliOptions {
  contentDir: string;
  outputDir: string;
}

export function printHelp(): void {
  console.log(`Usage: ssg build [options]

A static site generator that converts Markdown into HTML.

Commands:
  build    Generate the site from the content directory

Options:
  -c, --content <dir>   Content directory containing Markdown files (default: ${DEFAULT_CONTENT_DIR})
  -o, --output <dir>    Output directory for generated HTML (default: ${DEFAULT_OUTPUT_DIR})
  -h, --help            Show this help message
`);
}

export function parseArgs(argv: string[]): {
  command?: string;
  options: CliOptions;
  help: boolean;
} {
  const args = argv.slice(2);
  let command: string | undefined;
  const options: CliOptions = {
    contentDir: DEFAULT_CONTENT_DIR,
    outputDir: DEFAULT_OUTPUT_DIR,
  };
  let help = false;

  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    switch (arg) {
      case 'build':
        command = 'build';
        break;
      case '-h':
      case '--help':
        help = true;
        break;
      case '-c':
      case '--content': {
        const value = args[++i];
        if (!value || value.startsWith('-')) {
          throw new Error(`Missing value for option ${arg}`);
        }
        options.contentDir = value;
        break;
      }
      case '-o':
      case '--output': {
        const value = args[++i];
        if (!value || value.startsWith('-')) {
          throw new Error(`Missing value for option ${arg}`);
        }
        options.outputDir = value;
        break;
      }
      default:
        throw new Error(`Unknown option or command: ${arg}`);
    }
  }

  return { command, options, help };
}

export async function run(argv: string[]): Promise<void> {
  const parsed = parseArgs(argv);

  if (parsed.help || parsed.command !== 'build') {
    printHelp();
    return;
  }

  const options: BuildOptions = {
    contentDir: path.resolve(parsed.options.contentDir),
    outputDir: path.resolve(parsed.options.outputDir),
  };

  const pages = await buildSite(options);
  console.log(
    `Generated ${pages.length} page${pages.length === 1 ? '' : 's'} in ${options.outputDir}`
  );
}

if (require.main === module) {
  run(process.argv).catch((err: unknown) => {
    const message = err instanceof Error ? err.message : String(err);
    console.error(`ssg: ${message}`);
    process.exit(1);
  });
}
