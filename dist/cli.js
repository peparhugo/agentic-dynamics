#!/usr/bin/env node
"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.parseArgs = parseArgs;
exports.run = run;
exports.main = main;
const site_1 = require("./site");
const serve_1 = require("./serve");
function parseArgs(argv) {
    const args = argv.slice(2);
    const options = {};
    for (let i = 0; i < args.length; i += 1) {
        const arg = args[i];
        if (arg === '--content' || arg === '-c') {
            options.content = args[++i];
        }
        else if (arg === '--output' || arg === '-o') {
            options.output = args[++i];
        }
        else if (arg === '--templates' || arg === '-t') {
            options.templates = args[++i];
        }
        else if (arg === '--port' || arg === '-p') {
            const value = args[++i];
            if (value !== undefined) {
                options.port = Number(value);
            }
        }
        else if (arg.startsWith('--content=')) {
            options.content = arg.slice('--content='.length);
        }
        else if (arg.startsWith('--output=')) {
            options.output = arg.slice('--output='.length);
        }
        else if (arg.startsWith('--templates=')) {
            options.templates = arg.slice('--templates='.length);
        }
        else if (arg.startsWith('--port=')) {
            options.port = Number(arg.slice('--port='.length));
        }
        else if (arg === '--incremental') {
            options.incremental = true;
        }
        else if (arg === '--clean') {
            options.clean = true;
        }
        else if (!arg.startsWith('-')) {
            options.command = arg;
        }
    }
    return options;
}
function toServeOptions(options) {
    return {
        content: options.content,
        output: options.output,
        templates: options.templates,
        port: options.port,
    };
}
function run(argv) {
    const options = parseArgs(argv);
    if (options.command === 'serve') {
        return (0, serve_1.startServer)(toServeOptions(options));
    }
    if (options.command !== 'build') {
        throw new Error('Unknown command. Usage: ssg build|serve [--content <dir>] [--output <dir>]');
    }
    return (0, site_1.buildSite)({
        contentDir: options.content || './content',
        outputDir: options.output || './dist',
        templatesDir: options.templates,
        incremental: options.incremental,
        clean: options.clean,
    });
}
function main(argv = process.argv) {
    const options = parseArgs(argv);
    if (options.command === 'serve') {
        (0, serve_1.startServer)(toServeOptions(options))
            .then((handle) => {
            console.log(`Dev server listening on ${handle.address}`);
            console.log(`Watching ${options.content || './content'} and ${options.templates || './templates'}`);
            console.log(`Serving ${options.output || './dist'}`);
        })
            .catch((err) => {
            console.error(`Failed to start dev server: ${err.message}`);
            process.exitCode = 1;
        });
        return;
    }
    if (options.command !== 'build') {
        console.error('Usage: ssg build|serve [--content <dir>] [--output <dir>] [--port <n>]');
        process.exitCode = 1;
        return;
    }
    const result = (0, site_1.buildSite)({
        contentDir: options.content || './content',
        outputDir: options.output || './dist',
        templatesDir: options.templates,
        incremental: options.incremental,
        clean: options.clean,
    });
    const output = options.output || './dist';
    const stats = result.stats ?? {
        pagesBuilt: result.posts.length,
        pagesSkipped: 0,
        timeSavedMs: 0,
    };
    console.log(`Built ${stats.pagesBuilt} page(s), skipped ${stats.pagesSkipped}, saved ${stats.timeSavedMs}ms into ${output}`);
}
if (require.main === module) {
    main();
}
