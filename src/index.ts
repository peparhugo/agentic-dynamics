#!/usr/bin/env node

import { build } from './build';
import { serve } from './serve';
import { BuildOptions, ServeOptions } from './types';

function parseBuildArgs(argv: string[]): BuildOptions {
  const contentIdx = argv.indexOf('--content');
  const outputIdx = argv.indexOf('--output');
  const templatesIdx = argv.indexOf('--templates');

  return {
    contentDir: contentIdx !== -1 ? argv[contentIdx + 1] : './content',
    outputDir: outputIdx !== -1 ? argv[outputIdx + 1] : './dist',
    templatesDir: templatesIdx !== -1 ? argv[templatesIdx + 1] : undefined,
  };
}

function parseServeArgs(argv: string[]): ServeOptions {
  const buildOptions = parseBuildArgs(argv);
  const portIdx = argv.indexOf('--port');
  const port = portIdx !== -1 ? parseInt(argv[portIdx + 1], 10) : 3000;
  return {
    contentDir: buildOptions.contentDir,
    outputDir: buildOptions.outputDir,
    templatesDir: buildOptions.templatesDir,
    port: isNaN(port) ? 3000 : port,
  };
}

const args = process.argv.slice(2);
const command = args[0];

if (command === 'build') {
  const options = parseBuildArgs(args);
  try {
    build(options);
    console.log(`Site built successfully in ${options.outputDir}`);
  } catch (err) {
    console.error('Error building site:', (err as Error).message);
    process.exit(1);
  }
} else if (command === 'serve') {
  const options = parseServeArgs(args);
  serve(options);
} else {
  console.log('Usage: npx ssg build [--content <dir>] [--output <dir>] [--templates <dir>]');
  console.log('       npx ssg serve [--content <dir>] [--output <dir>] [--templates <dir>] [--port <port>]');
  process.exit(0);
}
