#!/usr/bin/env node
"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.parseArgs = parseArgs;
const parser_1 = require("./parser");
const generator_1 = require("./generator");
const server_1 = require("./server");
function parseArgs(args) {
    const command = args[0] || 'build';
    let contentDir = './content';
    let outputDir = './dist';
    let templatesDir = './templates';
    let port = 3000;
    for (let i = 0; i < args.length; i++) {
        if (args[i] === '--content' && i + 1 < args.length) {
            contentDir = args[i + 1];
            i++;
        }
        else if (args[i] === '--output' && i + 1 < args.length) {
            outputDir = args[i + 1];
            i++;
        }
        else if (args[i] === '--templates' && i + 1 < args.length) {
            templatesDir = args[i + 1];
            i++;
        }
        else if (args[i] === '--port' && i + 1 < args.length) {
            port = parseInt(args[i + 1], 10);
            if (isNaN(port) || port < 1 || port > 65535) {
                console.error(`Invalid port: ${args[i + 1]}`);
                process.exit(1);
            }
            i++;
        }
    }
    return { command, contentDir, outputDir, templatesDir, port };
}
function main() {
    const args = process.argv.slice(2);
    const { command, contentDir, outputDir, templatesDir, port } = parseArgs(args);
    if (command === 'serve') {
        (0, server_1.startDevServer)({ contentDir, outputDir, templatesDir, port });
        return;
    }
    if (command !== 'build') {
        console.error(`Unknown command: ${command}`);
        console.error('Usage: npx ssg build [--content <dir>] [--output <dir>] [--templates <dir>]');
        console.error('       npx ssg serve [--content <dir>] [--output <dir>] [--templates <dir>] [--port <port>]');
        process.exit(1);
    }
    try {
        const parseResult = (0, parser_1.parseFiles)({ contentDir, outputDir });
        (0, generator_1.generateSite)(parseResult, outputDir, templatesDir);
        console.log(`Site generated in ${outputDir}`);
    }
    catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        console.error(`Error: ${message}`);
        process.exit(1);
    }
}
if (require.main === module) {
    main();
}
