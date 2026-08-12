import path from 'path';
import { buildSite } from './build';
import { startDevServer } from './serve';
import { DEFAULT_TEMPLATE_DIR } from './template';
import { BuildOptions } from './types';

const DEFAULT_CONTENT_DIR = './content';
const DEFAULT_OUTPUT_DIR = './dist';
const DEFAULT_PORT = 3000;

export interface CliOptions {
  contentDir: string;
  outputDir: string;
  templateDir: string;
  port?: number;
  incremental?: boolean;
  clean?: boolean;
}

export function printHelp(): void {
  console.log(`Usage: ssg <command> [options]

A static site generator that converts Markdown into HTML.

Commands:
  build    Generate the site from the content directory
  serve    Start a live-reload development server

Options:
  -c, --content <dir>     Content directory containing Markdown files (default: ${DEFAULT_CONTENT_DIR})
  -o, --output <dir>      Output directory for generated HTML (default: ${DEFAULT_OUTPUT_DIR})
  -t, --templates <dir>   Template directory with .hbs templates (default: ${DEFAULT_TEMPLATE_DIR})
  -p, --port <port>       Port for the dev server (default: ${DEFAULT_PORT})
      --incremental       Only rebuild pages whose source or template changed
      --clean             Force a full rebuild, ignoring the cache
  -h, --help              Show this help message
`);
}

export function parseArgs(argv: string[]): {
  command?: string;
  options: CliOptions;
  help: boolean;
} {
  const args = argv.slice(2);
  let command: string | undefined;
  const options: CliOptions = {
    contentDir: DEFAULT_CONTENT_DIR,
    outputDir: DEFAULT_OUTPUT_DIR,
    templateDir: DEFAULT_TEMPLATE_DIR,
  };
  let help = false;

  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    switch (arg) {
      case 'build':
        command = 'build';
        break;
      case 'serve':
        command = 'serve';
        break;
      case '-h':
      case '--help':
        help = true;
        break;
      case '-c':
      case '--content': {
        const value = args[++i];
        if (!value || value.startsWith('-')) {
          throw new Error(`Missing value for option ${arg}`);
        }
        options.contentDir = value;
        break;
      }
      case '-o':
      case '--output': {
        const value = args[++i];
        if (!value || value.startsWith('-')) {
          throw new Error(`Missing value for option ${arg}`);
        }
        options.outputDir = value;
        break;
      }
      case '-t':
      case '--templates': {
        const value = args[++i];
        if (!value || value.startsWith('-')) {
          throw new Error(`Missing value for option ${arg}`);
        }
        options.templateDir = value;
        break;
      }
      case '-p':
      case '--port': {
        const value = args[++i];
        if (!value || value.startsWith('-')) {
          throw new Error(`Missing value for option ${arg}`);
        }
        const port = Number(value);
        if (!Number.isInteger(port) || port < 0 || port > 65535) {
          throw new Error(`Invalid port: ${value}`);
        }
        options.port = port;
        break;
      }
      case '--incremental':
        options.incremental = true;
        break;
      case '--clean':
        options.clean = true;
        break;
      default:
        throw new Error(`Unknown option or command: ${arg}`);
    }
  }

  return { command, options, help };
}

export async function run(argv: string[]): Promise<void> {
  const parsed = parseArgs(argv);

  if (parsed.help) {
    printHelp();
    return;
  }

  if (parsed.command === 'build') {
    const options: BuildOptions = {
      contentDir: path.resolve(parsed.options.contentDir),
      outputDir: path.resolve(parsed.options.outputDir),
      templateDir: path.resolve(parsed.options.templateDir),
      incremental: parsed.options.incremental,
      clean: parsed.options.clean,
    };

    const pages = await buildSite(options, (stats) => {
      if (parsed.options.incremental) {
        console.log(
          `Build stats: ${stats.built} built, ${stats.skipped} skipped, ` +
            `time saved ~${stats.timeSavedMs}ms`
        );
      }
    });
    console.log(
      `Generated ${pages.length} page${pages.length === 1 ? '' : 's'} in ${options.outputDir}`
    );
    return;
  }

  if (parsed.command === 'serve') {
    const options = {
      contentDir: path.resolve(parsed.options.contentDir),
      outputDir: path.resolve(parsed.options.outputDir),
      templateDir: path.resolve(parsed.options.templateDir),
      port: parsed.options.port,
    };

    const devServer = await startDevServer(options);
    console.log(
      `Serving ${options.outputDir} at http://${devServer.host}:${devServer.port}`
    );

    const shutdown = (): void => {
      devServer.close().then(() => process.exit(0)).catch(() => process.exit(1));
    };
    process.once('SIGINT', shutdown);
    process.once('SIGTERM', shutdown);
    return;
  }

  printHelp();
}

if (require.main === module) {
  run(process.argv).catch((err: unknown) => {
    const message = err instanceof Error ? err.message : String(err);
    console.error(`ssg: ${message}`);
    process.exit(1);
  });
}
