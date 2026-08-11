#!/usr/bin/env node

import { MarkdownPlugin } from './plugins/markdown';
import { TemplatePlugin } from './plugins/template';
import { DevServerPlugin } from './plugins/dev-server';
import { SsgEngine } from './ssg-engine';

export { SsgEngine } from './ssg-engine';
export { MarkdownPlugin } from './plugins/markdown';
export { TemplatePlugin } from './plugins/template';
export { DevServerPlugin } from './plugins/dev-server';

export function parseArgs(args: string[]): {
  contentDir: string;
  outputDir: string;
  templatesDir: string;
  command: string;
  port: number;
  incremental: boolean;
  clean: boolean;
} {
  const command = args[0] || 'build';
  let contentDir = './content';
  let outputDir = './dist';
  let templatesDir = './templates';
  let port = 3000;
  let incremental = false;
  let clean = false;

  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--content' && i + 1 < args.length) {
      contentDir = args[i + 1];
      i++;
    } else if (args[i] === '--output' && i + 1 < args.length) {
      outputDir = args[i + 1];
      i++;
    } else if (args[i] === '--templates' && i + 1 < args.length) {
      templatesDir = args[i + 1];
      i++;
    } else if (args[i] === '--port' && i + 1 < args.length) {
      port = parseInt(args[i + 1], 10);
      if (isNaN(port) || port < 1 || port > 65535) {
        console.error(`Invalid port: ${args[i + 1]}`);
        process.exit(1);
      }
      i++;
    } else if (args[i] === '--incremental') {
      incremental = true;
    } else if (args[i] === '--clean') {
      clean = true;
    }
  }

  return { command, contentDir, outputDir, templatesDir, port, incremental, clean };
}

async function main() {
  const args = process.argv.slice(2);
  const { command, contentDir, outputDir, templatesDir, port, incremental, clean } = parseArgs(args);

  const engine = new SsgEngine([
    new MarkdownPlugin(),
    new TemplatePlugin(),
  ]);

  if (command === 'serve') {
    const devServer = new DevServerPlugin(engine, incremental);
    devServer.serve({ contentDir, outputDir, templatesDir, port });
    return;
  }

  if (command !== 'build') {
    console.error(`Unknown command: ${command}`);
    console.error('Usage: npx ssg build [--content <dir>] [--output <dir>] [--templates <dir>] [--incremental] [--clean]');
    console.error('       npx ssg serve [--content <dir>] [--output <dir>] [--templates <dir>] [--port <port>]');
    process.exit(1);
  }

  try {
    await engine.build({ contentDir, outputDir, templatesDir, incremental, clean });
    console.log(`Site generated in ${outputDir}`);
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : String(err);
    console.error(`Error: ${message}`);
    process.exit(1);
  }
}

if (require.main === module) {
  main();
}
