import { build, buildIncremental } from './generate';
import { DevServer } from './server';
import { loadConfig, loadPlugins } from './config';

export interface CliOptions {
  command: string;
  contentDir: string;
  outputDir: string;
  templatesDir: string;
  port: number;
  incremental: boolean;
  clean: boolean;
}

export function parseArgs(argv: string[]): CliOptions {
  const args = argv.slice(2);
  const options: CliOptions = {
    command: '',
    contentDir: './content',
    outputDir: './dist',
    templatesDir: './templates',
    port: 3000,
    incremental: false,
    clean: false,
  };

  let i = 0;
  while (i < args.length) {
    const arg = args[i];
    if (arg === '--content') {
      options.contentDir = args[++i];
    } else if (arg === '--output') {
      options.outputDir = args[++i];
    } else if (arg === '--templates') {
      options.templatesDir = args[++i];
    } else if (arg === '--port') {
      options.port = Number(args[++i]);
    } else if (arg === '--incremental') {
      options.incremental = true;
    } else if (arg === '--clean') {
      options.clean = true;
    } else if (arg.startsWith('--content=')) {
      options.contentDir = arg.slice('--content='.length);
    } else if (arg.startsWith('--output=')) {
      options.outputDir = arg.slice('--output='.length);
    } else if (arg.startsWith('--templates=')) {
      options.templatesDir = arg.slice('--templates='.length);
    } else if (arg.startsWith('--port=')) {
      options.port = Number(arg.slice('--port='.length));
    } else if (!arg.startsWith('-')) {
      if (!options.command) options.command = arg;
    }
    i++;
  }

  return options;
}

function serve(options: CliOptions): number {
  const plugins = loadPlugins(loadConfig());
  const server = new DevServer({
    contentDir: options.contentDir,
    outputDir: options.outputDir,
    templatesDir: options.templatesDir,
    port: options.port,
    plugins,
  });

  server
    .start()
    .then(() => {
      console.log(`Serving ${options.outputDir} at http://localhost:${server.port()}`);
    })
    .catch((err) => {
      console.error(err instanceof Error ? err.message : String(err));
      process.exitCode = 1;
    });

  return 0;
}

export function run(argv: string[]): number {
  const options = parseArgs(argv);
  if (options.command === 'build') {
    try {
      const plugins = loadPlugins(loadConfig());
      const buildOptions = {
        contentDir: options.contentDir,
        outputDir: options.outputDir,
        templatesDir: options.templatesDir,
        incremental: options.incremental,
        clean: options.clean,
      };
      if (options.incremental || options.clean) {
        const result = buildIncremental(buildOptions, plugins);
        console.log(
          `Built ${result.stats.pagesBuilt} page(s), skipped ${result.stats.pagesSkipped} page(s), ` +
            `saved ${result.stats.timeSavedMs}ms in ${options.outputDir}`
        );
      } else {
        const pages = build(buildOptions, plugins);
        console.log(`Generated ${pages.length} page(s) in ${options.outputDir}`);
      }
      return 0;
    } catch (err) {
      console.error(err instanceof Error ? err.message : String(err));
      return 1;
    }
  }

  if (options.command === 'serve') {
    return serve(options);
  }

  console.error(
    'Usage: ssg build [--incremental] [--clean] [--content <dir>] [--output <dir>] [--templates <dir>]\n' +
      '       ssg serve [--port <port>] [--content <dir>] [--output <dir>] [--templates <dir>]'
  );
  return 1;
}

if (require.main === module) {
  const options = parseArgs(process.argv);
  const code = run(process.argv);
  if (options.command !== 'serve') {
    process.exit(code);
  }
}
