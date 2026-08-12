import { buildSite } from './builder';

export interface CliOptions {
  command: 'build';
  contentDir: string;
  outputDir: string;
}

export function parseArgs(argv: string[]): CliOptions {
  let command: 'build' = 'build';
  let contentDir = './content';
  let outputDir = './dist';

  const args = argv.slice(2);
  for (let i = 0; i < args.length; i += 1) {
    const arg = args[i];
    if (arg === 'build') {
      command = 'build';
    } else if (arg === '--content' || arg === '-c') {
      contentDir = args[i + 1] ?? contentDir;
      i += 1;
    } else if (arg.startsWith('--content=')) {
      contentDir = arg.slice('--content='.length);
    } else if (arg === '--output' || arg === '-o') {
      outputDir = args[i + 1] ?? outputDir;
      i += 1;
    } else if (arg.startsWith('--output=')) {
      outputDir = arg.slice('--output='.length);
    } else if (arg === '--help' || arg === '-h') {
      printHelp();
      process.exit(0);
    }
  }

  return { command, contentDir, outputDir };
}

export function printHelp(): void {
  const lines = [
    'Usage: ssg build [options]',
    '',
    'Generate a static site from Markdown files.',
    '',
    'Options:',
    '  --content <dir>   Content directory (default: ./content)',
    '  --output <dir>    Output directory (default: ./dist)',
    '  --help, -h        Show this help message',
  ];
  console.log(lines.join('\n'));
}

export function run(argv: string[]): void {
  const options = parseArgs(argv);
  const pages = buildSite(options.contentDir, options.outputDir);
  console.log(`Built ${pages.length} pages into ${options.outputDir}`);
}
