#!/usr/bin/env node
"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const generator_1 = require("./generator");
const server_1 = require("./server");
function parseBuildArgs(args) {
    const options = { content: './content', output: './dist' };
    let i = 3;
    while (i < args.length) {
        if (args[i] === '--content' && i + 1 < args.length) {
            options.content = args[i + 1];
            i += 2;
        }
        else if (args[i] === '--output' && i + 1 < args.length) {
            options.output = args[i + 1];
            i += 2;
        }
        else if (args[i] === '--templates' && i + 1 < args.length) {
            options.templates = args[i + 1];
            i += 2;
        }
        else {
            i += 1;
        }
    }
    return options;
}
function parseServeArgs(args) {
    const options = { content: './content', output: './dist', port: 3000 };
    let i = 3;
    while (i < args.length) {
        if (args[i] === '--port' && i + 1 < args.length) {
            options.port = parseInt(args[i + 1], 10);
            i += 2;
        }
        else if (args[i] === '--content' && i + 1 < args.length) {
            options.content = args[i + 1];
            i += 2;
        }
        else if (args[i] === '--output' && i + 1 < args.length) {
            options.output = args[i + 1];
            i += 2;
        }
        else if (args[i] === '--templates' && i + 1 < args.length) {
            options.templates = args[i + 1];
            i += 2;
        }
        else {
            i += 1;
        }
    }
    return options;
}
const command = process.argv[2];
if (!command || (command !== 'build' && command !== 'serve')) {
    console.error('Usage: npx ssg build [--content <dir>] [--output <dir>] [--templates <dir>]');
    console.error('       npx ssg serve [--content <dir>] [--output <dir>] [--templates <dir>] [--port <port>]');
    process.exit(1);
}
if (command === 'build') {
    const options = parseBuildArgs(process.argv);
    const count = (0, generator_1.generateSite)(options.content, options.output, options.templates);
    process.exit(count > 0 ? 0 : 1);
}
else {
    const options = parseServeArgs(process.argv);
    (0, server_1.startServer)({
        content: options.content,
        output: options.output,
        templates: options.templates,
        port: options.port,
    });
}
//# sourceMappingURL=index.js.map