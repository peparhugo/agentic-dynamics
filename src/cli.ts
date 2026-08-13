import { build } from './build';
import { serve, ServeHandle } from './serve';

export interface CliArgs {
  command: string;
  contentDir: string;
  outputDir: string;
  templatesDir?: string;
  port?: number;
}

const DEFAULT_CONTENT_DIR = './content';
const DEFAULT_OUTPUT_DIR = './dist';
const DEFAULT_PORT = 3000;

export function parseArgs(argv: string[]): CliArgs {
  const [command = 'build', ...rest] = argv;
  let contentDir = DEFAULT_CONTENT_DIR;
  let outputDir = DEFAULT_OUTPUT_DIR;
  let templatesDir: string | undefined;
  let port: number | undefined;

  for (let i = 0; i < rest.length; i++) {
    const arg = rest[i];
    if (arg === '--content') {
      const value = rest[i + 1];
      if (!value) throw new Error('--content requires a directory argument');
      contentDir = value;
      i++;
    } else if (arg === '--output') {
      const value = rest[i + 1];
      if (!value) throw new Error('--output requires a directory argument');
      outputDir = value;
      i++;
    } else if (arg === '--templates') {
      const value = rest[i + 1];
      if (!value) throw new Error('--templates requires a directory argument');
      templatesDir = value;
      i++;
    } else if (arg === '--port') {
      const value = rest[i + 1];
      if (!value) throw new Error('--port requires a numeric argument');
      const parsed = Number(value);
      if (!Number.isInteger(parsed) || parsed < 0) throw new Error('--port requires a numeric argument');
      port = parsed;
      i++;
    } else {
      throw new Error(`Unknown argument: ${arg}`);
    }
  }

  return {
    command,
    contentDir,
    outputDir,
    ...(templatesDir !== undefined ? { templatesDir } : {}),
    ...(port !== undefined ? { port } : {}),
  };
}

export function run(argv: string[]): ServeHandle | void {
  const args = parseArgs(argv);

  if (args.command === 'build') {
    const result = build({ contentDir: args.contentDir, outputDir: args.outputDir, templatesDir: args.templatesDir });
    // eslint-disable-next-line no-console
    console.log(`Built ${result.pages.length} page(s) from ${args.contentDir} to ${args.outputDir}`);
    return;
  }

  if (args.command === 'serve') {
    const handle = serve({
      contentDir: args.contentDir,
      outputDir: args.outputDir,
      templatesDir: args.templatesDir,
      port: args.port ?? DEFAULT_PORT,
    });
    // eslint-disable-next-line no-console
    console.log(
      `Serving ${args.outputDir} at http://localhost:${handle.port} (watching ${args.contentDir}, ${
        args.templatesDir ?? './templates'
      })`
    );
    return handle;
  }

  throw new Error(`Unknown command: ${args.command}. Supported commands: build, serve`);
}

export function main(): void {
  try {
    run(process.argv.slice(2));
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    // eslint-disable-next-line no-console
    console.error(`ssg: ${message}`);
    process.exitCode = 1;
  }
}

if (require.main === module) {
  main();
}
