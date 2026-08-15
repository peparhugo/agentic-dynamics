export interface CliArgs {
  command: string;
  contentDir: string;
  outputDir: string;
}

export function parseArgs(argv: string[]): CliArgs {
  const args: CliArgs = {
    command: 'build',
    contentDir: './content',
    outputDir: './dist'
  };

  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];

    if (arg === '--content' && i + 1 < argv.length) {
      args.contentDir = argv[++i];
    } else if (arg === '--output' && i + 1 < argv.length) {
      args.outputDir = argv[++i];
    } else if (arg === 'build') {
      args.command = 'build';
    }
  }

  return args;
}
