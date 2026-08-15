export interface CliArgs {
  command: string;
  contentDir: string;
  outputDir: string;
  port?: number;
  incremental?: boolean;
  clean?: boolean;
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
    } else if (arg === '--port' && i + 1 < argv.length) {
      args.port = parseInt(argv[++i], 10);
    } else if (arg === '--incremental') {
      args.incremental = true;
    } else if (arg === '--clean') {
      args.clean = true;
    } else if (arg === 'build') {
      args.command = 'build';
    } else if (arg === 'serve') {
      args.command = 'serve';
    }
  }

  return args;
}
