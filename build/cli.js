#!/usr/bin/env node
"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const parser_1 = require("./parser");
const generator_1 = require("./generator");
const server_1 = require("./server");
function parseArgs(args) {
    let content = 'content';
    let output = 'dist';
    let templates = 'templates';
    let port = 3000;
    let i = 0;
    while (i < args.length) {
        if (args[i] === '--content' && i + 1 < args.length) {
            content = args[i + 1];
            i += 2;
        }
        else if (args[i] === '--output' && i + 1 < args.length) {
            output = args[i + 1];
            i += 2;
        }
        else if (args[i] === '--templates' && i + 1 < args.length) {
            templates = args[i + 1];
            i += 2;
        }
        else if (args[i] === '--port' && i + 1 < args.length) {
            port = parseInt(args[i + 1], 10);
            i += 2;
        }
        else {
            i++;
        }
    }
    return { content, output, templates, port };
}
const command = process.argv[2];
if (command === 'build') {
    const { content, output, templates } = parseArgs(process.argv.slice(3));
    const pages = (0, parser_1.parseDirectory)(content);
    (0, generator_1.generateSite)(pages, output, templates);
    console.log(`Site generated in ${output} (${pages.length} pages)`);
}
else if (command === 'serve') {
    const { content, output, templates, port } = parseArgs(process.argv.slice(3));
    const pages = (0, parser_1.parseDirectory)(content);
    (0, generator_1.generateSite)(pages, output, templates);
    console.log(`Site generated in ${output} (${pages.length} pages)`);
    (0, server_1.startServer)({ port, content, output, templates });
}
else {
    console.log('Usage: npx ssg build [--content <dir>] [--output <dir>] [--templates <dir>]\n' +
        '       npx ssg serve [--content <dir>] [--output <dir>] [--templates <dir>] [--port <port>]');
    process.exit(command ? 1 : 0);
}
//# sourceMappingURL=cli.js.map