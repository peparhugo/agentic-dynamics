import { buildSite } from './generator';
import { startDevServer } from './server';

function usage(): void {
  console.error('Usage: ssg build [--content <dir>] [--output <dir>] [--templates <dir>]');
  console.error('       ssg serve [--content <dir>] [--output <dir>] [--templates <dir>] [--port <number>]');
}

function option(args: string[], name: string): string | undefined {
  const index = args.indexOf(name);
  if (index === -1) return undefined;
  const value = args[index + 1];
  if (!value || value.startsWith('--')) throw new Error(`Missing value for ${name}`);
  return value;
}

async function main(): Promise<void> {
  const args = process.argv.slice(2);
  if (args[0] !== 'build' && args[0] !== 'serve') {
    usage();
    process.exitCode = 1;
    return;
  }
  try {
    if (args[0] === 'serve') {
      const portValue = option(args, '--port');
      const port = portValue === undefined ? undefined : Number(portValue);
      if (port !== undefined && (!Number.isInteger(port) || port < 0 || port > 65535)) {
        throw new Error('Port must be an integer between 0 and 65535');
      }
      const server = await startDevServer({
        contentDir: option(args, '--content'),
        outputDir: option(args, '--output'),
        templatesDir: option(args, '--templates'),
        port,
      });
      console.log(`Serving at http://localhost:${server.port}`);
      return;
    }
    const pages = await buildSite({
      contentDir: option(args, '--content'),
      outputDir: option(args, '--output'),
      templatesDir: option(args, '--templates'),
    });
    console.log(`Built ${pages.length} page${pages.length === 1 ? '' : 's'}.`);
  } catch (error) {
    console.error(error instanceof Error ? error.message : error);
    process.exitCode = 1;
  }
}

void main();
