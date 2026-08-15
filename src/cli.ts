import { build } from './generate';

export interface CliOptions {
  command: string;
  contentDir: string;
  outputDir: string;
  templatesDir: string;
}

export function parseArgs(argv: string[]): CliOptions {
  const args = argv.slice(2);
  const options: CliOptions = {
    command: '',
    contentDir: './content',
    outputDir: './dist',
    templatesDir: './templates',
  };

  let i = 0;
  while (i < args.length) {
    const arg = args[i];
    if (arg === '--content') {
      options.contentDir = args[++i];
    } else if (arg === '--output') {
      options.outputDir = args[++i];
    } else if (arg === '--templates') {
      options.templatesDir = args[++i];
    } else if (arg.startsWith('--content=')) {
      options.contentDir = arg.slice('--content='.length);
    } else if (arg.startsWith('--output=')) {
      options.outputDir = arg.slice('--output='.length);
    } else if (arg.startsWith('--templates=')) {
      options.templatesDir = arg.slice('--templates='.length);
    } else if (!arg.startsWith('-')) {
      if (!options.command) options.command = arg;
    }
    i++;
  }

  return options;
}

export function run(argv: string[]): number {
  const options = parseArgs(argv);
  if (options.command !== 'build') {
    console.error('Usage: ssg build [--content <dir>] [--output <dir>] [--templates <dir>]');
    return 1;
  }

  try {
    const pages = build({
      contentDir: options.contentDir,
      outputDir: options.outputDir,
      templatesDir: options.templatesDir,
    });
    console.log(`Generated ${pages.length} page(s) in ${options.outputDir}`);
    return 0;
  } catch (err) {
    console.error(err instanceof Error ? err.message : String(err));
    return 1;
  }
}

if (require.main === module) {
  process.exit(run(process.argv));
}
