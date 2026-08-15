export interface ParsedArgs {
  command: string | null;
  contentDir: string;
  outputDir: string;
  templatesDir: string;
  help: boolean;
}

export function parseArgs(argv: string[]): ParsedArgs {
  const result: ParsedArgs = {
    command: null,
    contentDir: './content',
    outputDir: './dist',
    templatesDir: './templates',
    help: false,
  };

  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];

    if (arg === '--help') {
      result.help = true;
    } else if (arg === '--content' && i + 1 < argv.length) {
      result.contentDir = argv[++i];
    } else if (arg === '--output' && i + 1 < argv.length) {
      result.outputDir = argv[++i];
    } else if (arg === '--templates' && i + 1 < argv.length) {
      result.templatesDir = argv[++i];
    } else if (!arg.startsWith('--') && result.command === null) {
      result.command = arg;
    }
  }

  return result;
}
