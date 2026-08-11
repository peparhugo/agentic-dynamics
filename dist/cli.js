#!/usr/bin/env node
"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const index_1 = require("./index");
const server_1 = require("./server");
function parseArgs(args) {
    const options = { content: './content', output: './dist', templates: './templates', port: 3000 };
    for (let i = 0; i < args.length; i++) {
        if (args[i] === '--content' && i + 1 < args.length) {
            options.content = args[i + 1];
            i++;
        }
        else if (args[i] === '--output' && i + 1 < args.length) {
            options.output = args[i + 1];
            i++;
        }
        else if (args[i] === '--templates' && i + 1 < args.length) {
            options.templates = args[i + 1];
            i++;
        }
        else if (args[i] === '--port' && i + 1 < args.length) {
            options.port = parseInt(args[i + 1], 10) || 3000;
            i++;
        }
        else if (args[i] === '--config' && i + 1 < args.length) {
            options.config = args[i + 1];
            i++;
        }
    }
    return options;
}
function loadCliConfig(options) {
    if (!options.config)
        return options;
    try {
        const configPath = require('path').resolve(options.config);
        const mod = require(configPath);
        const cfg = mod.default || mod;
        return {
            content: cfg.contentDir || options.content,
            output: cfg.outputDir || options.output,
            templates: cfg.templatesDir || options.templates,
            port: cfg.port || options.port,
        };
    }
    catch {
        return options;
    }
}
const args = process.argv.slice(2);
if (args.length === 0 || (args[0] !== 'build' && args[0] !== 'serve')) {
    console.error('Usage: ssg build|serve [--content <dir>] [--output <dir>] [--templates <dir>] [--port <port>] [--config <file>]');
    process.exit(1);
}
const cliOptions = parseArgs(args.slice(1));
const options = loadCliConfig(cliOptions);
if (args[0] === 'build') {
    const pages = (0, index_1.parseMarkdownFiles)(options.content);
    (0, index_1.generateSite)(pages, options.output, options.templates);
    console.log(`Generated ${pages.length} page(s) in ${options.output}`);
}
else if (args[0] === 'serve') {
    (0, server_1.serve)(options);
}
//# sourceMappingURL=cli.js.map