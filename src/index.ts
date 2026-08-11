#!/usr/bin/env node

import { build } from './build';
import { BuildOptions } from './types';

function parseArgs(argv: string[]): BuildOptions {
  const contentIdx = argv.indexOf('--content');
  const outputIdx = argv.indexOf('--output');
  const templatesIdx = argv.indexOf('--templates');

  return {
    contentDir: contentIdx !== -1 ? argv[contentIdx + 1] : './content',
    outputDir: outputIdx !== -1 ? argv[outputIdx + 1] : './dist',
    templatesDir: templatesIdx !== -1 ? argv[templatesIdx + 1] : undefined,
  };
}

const args = process.argv.slice(2);
const command = args[0];

if (command === 'build') {
  const options = parseArgs(args);
  try {
    build(options);
    console.log(`Site built successfully in ${options.outputDir}`);
  } catch (err) {
    console.error('Error building site:', (err as Error).message);
    process.exit(1);
  }
} else {
  console.log('Usage: npx ssg build [--content <dir>] [--output <dir>] [--templates <dir>]');
  process.exit(0);
}
