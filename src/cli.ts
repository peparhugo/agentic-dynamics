import { build } from './build';
import { DevServer } from './dev-server';

export interface ParsedArgs {
  command: string;
  content: string;
  output: string;
  templates: string;
  port: number;
  incremental: boolean;
  clean: boolean;
}

export function parseArgs(argv: string[]): ParsedArgs {
  const args = argv.slice(2);
  const command = args.find((a) => !a.startsWith('-')) || 'build';
  let content = './content';
  let output = './dist';
  let templates = './templates';
  let port = 3000;
  let incremental = false;
  let clean = false;

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
    } else if (arg === '--templates' || arg === '-t') {
      templates = args[i + 1] ?? templates;
      i++;
    } else if (arg.startsWith('--templates=')) {
      templates = arg.slice('--templates='.length);
    } else if (arg === '--port' || arg === '-p') {
      const value = args[i + 1];
      if (value !== undefined) {
        port = Number(value);
        i++;
      }
    } else if (arg.startsWith('--port=')) {
      port = Number(arg.slice('--port='.length));
    } else if (arg === '--incremental') {
      incremental = true;
    } else if (arg === '--clean') {
      clean = true;
    }
  }

  if (Number.isNaN(port)) {
    port = 3000;
  }

  return { command, content, output, templates, port, incremental, clean };
}

export function run(argv: string[]): void {
  const { command, content, output, templates, port, incremental, clean } = parseArgs(argv);

  if (command === 'build') {
    const result = build({
      contentDir: content,
      outputDir: output,
      templatesDir: templates,
      incremental,
      clean,
    });
    const { pagesBuilt, pagesSkipped, timeSavedMs } = result.stats;
    console.log(
      `Built ${result.writtenFiles.length} file(s) into ${result.outputDir} ` +
        `(${pagesBuilt} built, ${pagesSkipped} skipped, ~${timeSavedMs}ms saved)`
    );
    return;
  }

  if (command === 'serve') {
    const server = new DevServer({
      contentDir: content,
      outputDir: output,
      templatesDir: templates,
      port,
    });
    server
      .start()
      .then((actualPort) => {
        console.log(`Serving ${output} at http://localhost:${actualPort}`);
      })
      .catch((err) => {
        console.error(`Failed to start dev server: ${err.message}`);
        process.exitCode = 1;
      });
    return;
  }

  console.error(`Unknown command: ${command}`);
  console.error('Usage: ssg build [--content <dir>] [--output <dir>]');
  process.exitCode = 1;
}
