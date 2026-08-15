export interface ParsedArgs {
  command: string | null;
  contentDir: string;
  outputDir: string;
  help: boolean;
}

export function parseArgs(argv: string[]): ParsedArgs {
  const result: ParsedArgs = {
    command: argv[0] || null,
    contentDir: './content',
    outputDir: './dist',
    help: false,
  };

  for (let i = 1; i < argv.length; i++) {
    const arg = argv[i];

    if (arg === '--help') {
      result.help = true;
    } else if (arg === '--content' && i + 1 < argv.length) {
      result.contentDir = argv[++i];
    } else if (arg === '--output' && i + 1 < argv.length) {
      result.outputDir = argv[++i];
    }
  }

  return result;
}
