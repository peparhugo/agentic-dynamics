import { build } from './build';

interface ParsedArgs {
  command: string;
  content: string;
  output: string;
}

export function parseArgs(argv: string[]): ParsedArgs {
  const args = argv.slice(2);
  const command = args.find((a) => !a.startsWith('-')) || 'build';
  let content = './content';
  let output = './dist';

  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    if (arg === '--content' || arg === '-c') {
      content = args[i + 1] ?? content;
      i++;
    } else if (arg.startsWith('--content=')) {
      content = arg.slice('--content='.length);
    } else if (arg === '--output' || arg === '-o') {
      output = args[i + 1] ?? output;
      i++;
    } else if (arg.startsWith('--output=')) {
      output = arg.slice('--output='.length);
    }
  }

  return { command, content, output };
}

export function run(argv: string[]): void {
  const { command, content, output } = parseArgs(argv);

  if (command === 'build') {
    const result = build({ contentDir: content, outputDir: output });
    console.log(`Built ${result.writtenFiles.length} files into ${result.outputDir}`);
    return;
  }

  console.error(`Unknown command: ${command}`);
  console.error('Usage: ssg build [--content <dir>] [--output <dir>]');
  process.exitCode = 1;
}
