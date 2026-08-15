#!/usr/bin/env node

import * as path from 'path';
import { SiteGenerator } from './generator.js';

function parseArgs(args: string[]): { command: string; contentDir: string; outputDir: string } {
  let command = 'build';
  let contentDir = './content';
  let outputDir = './dist';

  for (let i = 0; i < args.length; i++) {
    const arg = args[i];

    if (!arg.startsWith('-')) {
      command = arg;
      continue;
    }

    if (arg === '--content' && i + 1 < args.length) {
      contentDir = args[++i];
    } else if (arg === '--output' && i + 1 < args.length) {
      outputDir = args[++i];
    }
  }

  return { command, contentDir, outputDir };
}

async function main(): Promise<void> {
  const args = process.argv.slice(2);
  const { command, contentDir, outputDir } = parseArgs(args);

  if (command !== 'build') {
    console.error(`Unknown command: ${command}`);
    process.exit(1);
  }

  const resolvedContentDir = path.resolve(contentDir);
  const resolvedOutputDir = path.resolve(outputDir);

  try {
    const generator = new SiteGenerator({
      contentDir: resolvedContentDir,
      outputDir: resolvedOutputDir,
    });

    await generator.build();
  } catch (error) {
    console.error('Error building site:', error instanceof Error ? error.message : String(error));
    process.exit(1);
  }
}

main();
