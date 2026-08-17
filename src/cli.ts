import { build } from './builder';

export interface CliOptions {
  command: string;
  content: string;
  output: string;
  templates: string;
}

export function parseArgs(argv: string[]): CliOptions {
  const options: CliOptions = {
    command: '',
    content: './content',
    output: './dist',
    templates: './templates',
  };

  let i = 0;
  while (i < argv.length) {
    const arg = argv[i];

    if (arg === 'build') {
      options.command = 'build';
      i += 1;
    } else if (arg === '--content' || arg === '-c') {
      if (i + 1 < argv.length) {
        options.content = argv[i + 1];
        i += 2;
      } else {
        i += 1;
      }
    } else if (arg.startsWith('--content=')) {
      options.content = arg.slice('--content='.length);
      i += 1;
    } else if (arg === '--output' || arg === '-o') {
      if (i + 1 < argv.length) {
        options.output = argv[i + 1];
        i += 2;
      } else {
        i += 1;
      }
    } else if (arg.startsWith('--output=')) {
      options.output = arg.slice('--output='.length);
      i += 1;
    } else if (arg === '--templates' || arg === '-t') {
      if (i + 1 < argv.length) {
        options.templates = argv[i + 1];
        i += 2;
      } else {
        i += 1;
      }
    } else if (arg.startsWith('--templates=')) {
      options.templates = arg.slice('--templates='.length);
      i += 1;
    } else if (arg === '--help' || arg === '-h') {
      options.command = 'help';
      i += 1;
    } else {
      i += 1;
    }
  }

  return options;
}

function printHelp(): void {
  const text = `Usage: ssg build [options]

Build a static site from a directory of Markdown files.

Options:
  --content <dir>     Directory containing Markdown files (default: ./content)
  --output <dir>      Directory to write generated HTML (default: ./dist)
  --templates <dir>   Directory containing templates (default: ./templates)
  -h, --help          Show this help message
`;
  process.stdout.write(text);
}

export function runCli(argv: string[]): number {
  const options = parseArgs(argv);

  if (options.command === 'help') {
    printHelp();
    return 0;
  }

  if (options.command === '') {
    printHelp();
    return 1;
  }

  if (options.command !== 'build') {
    process.stderr.write(`Unknown command: ${options.command}\n`);
    printHelp();
    return 1;
  }

  const result = build({
    contentDir: options.content,
    outputDir: options.output,
    templatesDir: options.templates,
  });

  process.stdout.write(
    `Built ${result.pages.length} page(s) to ${result.outputDir}\n`
  );
  return 0;
}
