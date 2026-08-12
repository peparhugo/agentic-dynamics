import {
  buildSite,
  DEFAULT_CONTENT_DIR,
  DEFAULT_OUTPUT_DIR,
} from './site';
import { DEFAULT_TEMPLATES_DIR } from './template';
import { serve, DEFAULT_PORT } from './serve';

export interface CliOptions {
  contentDir: string;
  outputDir: string;
  templatesDir: string;
  port?: number;
}

export interface ParsedArgs {
  command: string;
  options: CliOptions;
}

export function printHelp(): void {
  console.log(
    [
      'Usage: ssg <command> [options]',
      '',
      'Commands:',
      '  build    generate a static site from Markdown files',
      '  serve    start a development server with live reload',
      '',
      'Options:',
      '  --content <dir>    directory containing Markdown files (default: ./content)',
      '  --output <dir>     directory to write the generated site (default: ./dist)',
      '  --templates <dir>  directory containing templates (default: ./templates)',
      '  --port <number>    port for the serve command (default: 3000)',
      '  -h, --help         show this help message',
    ].join('\n')
  );
}

export function parseArgs(argv: string[]): ParsedArgs {
  const args = [...argv];
  let command = 'build';
  if (args.length > 0 && !args[0].startsWith('-')) {
    command = args.shift() as string;
  }

  const options: CliOptions = {
    contentDir: DEFAULT_CONTENT_DIR,
    outputDir: DEFAULT_OUTPUT_DIR,
    templatesDir: DEFAULT_TEMPLATES_DIR,
  };

  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    if (arg === '--content' || arg === '-c') {
      const value = args[++i];
      if (value === undefined) {
        throw new Error(`missing value for ${arg}`);
      }
      options.contentDir = value;
    } else if (arg === '--output' || arg === '-o') {
      const value = args[++i];
      if (value === undefined) {
        throw new Error(`missing value for ${arg}`);
      }
      options.outputDir = value;
    } else if (arg === '--templates' || arg === '-t') {
      const value = args[++i];
      if (value === undefined) {
        throw new Error(`missing value for ${arg}`);
      }
      options.templatesDir = value;
    } else if (arg === '--port' || arg === '-p') {
      const value = args[++i];
      if (value === undefined) {
        throw new Error(`missing value for ${arg}`);
      }
      const port = Number(value);
      if (!Number.isInteger(port) || port < 0 || port > 65535) {
        throw new Error(`invalid port: ${value}`);
      }
      options.port = port;
    } else if (arg === '--help' || arg === '-h') {
      printHelp();
      process.exit(0);
    } else {
      throw new Error(`unknown argument: ${arg}`);
    }
  }

  return { command, options };
}

function serveCommand(options: CliOptions): void {
  try {
    const handle = serve({
      contentDir: options.contentDir,
      outputDir: options.outputDir,
      templatesDir: options.templatesDir,
      port: options.port ?? DEFAULT_PORT,
    });
    const port = handle.port;
    console.log(`Serving ${options.outputDir} at http://localhost:${port}`);
    console.log('Watching for changes...');
    let closing = false;
    const shutdown = (): void => {
      if (closing) return;
      closing = true;
      handle.close().then(() => process.exit(0));
    };
    process.on('SIGINT', shutdown);
    process.on('SIGTERM', shutdown);
  } catch (err) {
    console.error(err instanceof Error ? err.message : String(err));
    process.exit(1);
  }
}

export function run(argv: string[]): void {
  let parsed: ParsedArgs;
  try {
    parsed = parseArgs(argv);
  } catch (err) {
    console.error(err instanceof Error ? err.message : String(err));
    process.exit(1);
  }

  if (parsed.command === 'serve') {
    serveCommand(parsed.options);
    return;
  }

  if (parsed.command !== 'build') {
    console.error(`unknown command: ${parsed.command}`);
    process.exit(1);
  }

  try {
    const result = buildSite(
      parsed.options.contentDir,
      parsed.options.outputDir,
      parsed.options.templatesDir
    );
    const pagesWord = result.pages === 1 ? 'page' : 'pages';
    console.log(`Built ${result.pages} ${pagesWord} into ${result.outputDir}`);
  } catch (err) {
    console.error(err instanceof Error ? err.message : String(err));
    process.exit(1);
  }
}
