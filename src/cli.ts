import { build } from './build';

export interface CliArgs {
  command: string;
  contentDir: string;
  outputDir: string;
  templatesDir?: string;
}

const DEFAULT_CONTENT_DIR = './content';
const DEFAULT_OUTPUT_DIR = './dist';

export function parseArgs(argv: string[]): CliArgs {
  const [command = 'build', ...rest] = argv;
  let contentDir = DEFAULT_CONTENT_DIR;
  let outputDir = DEFAULT_OUTPUT_DIR;
  let templatesDir: string | undefined;

  for (let i = 0; i < rest.length; i++) {
    const arg = rest[i];
    if (arg === '--content') {
      const value = rest[i + 1];
      if (!value) throw new Error('--content requires a directory argument');
      contentDir = value;
      i++;
    } else if (arg === '--output') {
      const value = rest[i + 1];
      if (!value) throw new Error('--output requires a directory argument');
      outputDir = value;
      i++;
    } else if (arg === '--templates') {
      const value = rest[i + 1];
      if (!value) throw new Error('--templates requires a directory argument');
      templatesDir = value;
      i++;
    } else {
      throw new Error(`Unknown argument: ${arg}`);
    }
  }

  return { command, contentDir, outputDir, ...(templatesDir !== undefined ? { templatesDir } : {}) };
}

export function run(argv: string[]): void {
  const args = parseArgs(argv);

  if (args.command !== 'build') {
    throw new Error(`Unknown command: ${args.command}. Supported commands: build`);
  }

  const result = build({ contentDir: args.contentDir, outputDir: args.outputDir, templatesDir: args.templatesDir });
  // eslint-disable-next-line no-console
  console.log(`Built ${result.pages.length} page(s) from ${args.contentDir} to ${args.outputDir}`);
}

export function main(): void {
  try {
    run(process.argv.slice(2));
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    // eslint-disable-next-line no-console
    console.error(`ssg: ${message}`);
    process.exitCode = 1;
  }
}

if (require.main === module) {
  main();
}
