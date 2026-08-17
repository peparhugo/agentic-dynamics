#!/usr/bin/env node
"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const index_1 = require("./index");
const serve_1 = require("./serve");
const VALUE_OPTIONS = {
    '--content': 'content',
    '--output': 'output',
    '--templates': 'templates',
    '--port': 'port',
};
function printHelp(command) {
    if (command === 'serve') {
        console.log(`Usage: npx ssg serve [options]

Start a live-reload development server.

Options:
  --content <dir>    Content directory containing Markdown files (default: ./content)
  --templates <dir>  Templates directory (default: ./templates)
  --output <dir>     Output directory to build and serve from (default: ./dist)
  --port <port>      Port to listen on (default: 3000)
  -h, --help         Show this help message
`);
        return;
    }
    console.log(`Usage: npx ssg build [options]

Generate a static site from Markdown files.

Options:
  --content <dir>   Content directory containing Markdown files (default: ./content)
  --output <dir>    Output directory for generated HTML (default: ./dist)
  -h, --help        Show this help message

Commands:
  build             Generate a static site from Markdown files
  serve             Start a live-reload development server on localhost:3000
`);
}
function parseArgs(args) {
    const options = {};
    for (let i = 0; i < args.length; i++) {
        const arg = args[i];
        if (arg === '-h' || arg === '--help') {
            return { options, help: true };
        }
        const eq = arg.indexOf('=');
        if (arg.startsWith('--') && eq !== -1) {
            const key = arg.slice(0, eq);
            const value = arg.slice(eq + 1);
            if (!(key in VALUE_OPTIONS)) {
                console.error(`Error: unknown option ${key}`);
                process.exit(2);
            }
            options[VALUE_OPTIONS[key]] = value;
            continue;
        }
        if (arg in VALUE_OPTIONS) {
            const value = args[i + 1];
            if (value === undefined || value.startsWith('--')) {
                console.error(`Error: option ${arg} requires a value`);
                process.exit(2);
            }
            options[VALUE_OPTIONS[arg]] = value;
            i++;
            continue;
        }
        console.error(`Error: unknown option ${arg}`);
        process.exit(2);
    }
    return { options, help: false };
}
function resolvePort(value) {
    if (value === undefined) {
        return 3000;
    }
    const port = Number(value);
    if (!Number.isInteger(port) || port < 0 || port > 65535) {
        console.error(`Error: invalid port "${value}"`);
        process.exit(2);
    }
    return port;
}
function main() {
    const args = process.argv.slice(2);
    const command = args[0];
    if (!command || command === '-h' || command === '--help' || command === 'help') {
        printHelp();
        process.exit(0);
    }
    if (command !== 'build' && command !== 'serve') {
        console.error(`Error: unknown command "${command}"`);
        printHelp();
        process.exit(1);
    }
    const { options, help } = parseArgs(args.slice(1));
    if (help) {
        printHelp(command);
        process.exit(0);
    }
    if (command === 'serve') {
        const port = resolvePort(options.port);
        (0, serve_1.startDevServer)({
            contentDir: options.content ?? 'content',
            outputDir: options.output ?? 'dist',
            templatesDir: options.templates ?? 'templates',
            port,
        })
            .then((server) => {
            console.log(`Serving ${server.outputDir} at http://localhost:${server.port}`);
        })
            .catch((err) => {
            console.error(`Error: ${err.message}`);
            process.exit(1);
        });
        return;
    }
    const site = (0, index_1.buildSite)({
        contentDir: options.content ?? 'content',
        outputDir: options.output ?? 'dist',
        templatesDir: options.templates ?? 'templates',
    });
    console.log(`Generated ${site.pages.length} page(s) in ${site.outputDir}`);
}
main();
//# sourceMappingURL=cli.js.map