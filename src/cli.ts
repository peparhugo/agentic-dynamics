#!/usr/bin/env node
import { build } from './build';
import { serve } from './serve';

interface ParsedArgs {
  command?: string;
  content: string;
  output: string;
  port: number;
}

function parseArgs(argv: string[]): ParsedArgs {
  const result: ParsedArgs = {
    command: argv[0],
    content: './content',
    output: './dist',
    port: 3000,
  };
  for (let i = 1; i < argv.length; i++) {
    const arg = argv[i];
    if (arg === '--content') {
      result.content = argv[++i] ?? result.content;
    } else if (arg === '--output') {
      result.output = argv[++i] ?? result.output;
    } else if (arg === '--port') {
      const value = Number(argv[++i]);
      if (Number.isFinite(value) && value >= 0) {
        result.port = value;
      }
    }
  }
  return result;
}

async function main(): Promise<void> {
  const args = parseArgs(process.argv.slice(2));

  if (args.command === 'build') {
    const pages = await build({ content: args.content, output: args.output });
    console.log(`Built ${pages.length} page(s) into ${args.output}.`);
    return;
  }

  if (args.command === 'serve') {
    const devServer = await serve({
      content: args.content,
      output: args.output,
      port: args.port,
    });
    console.log(`Serving ${args.output} at http://localhost:${devServer.port}`);
    return;
  }

  console.error('Usage: ssg build [--content <dir>] [--output <dir>]');
  console.error('       ssg serve [--content <dir>] [--output <dir>] [--port <port>]');
  process.exit(1);
}

main().catch((err) => {
  console.error(err instanceof Error ? err.message : err);
  process.exit(1);
});
