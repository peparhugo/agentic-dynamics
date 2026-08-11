#!/usr/bin/env node
"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const commander_1 = require("commander");
const path_1 = __importDefault(require("path"));
const build_1 = require("./build");
const serve_1 = require("./serve");
const program = new commander_1.Command();
program
    .name('ssg')
    .description('A static site generator')
    .version('1.0.0');
program
    .command('build')
    .description('Build the static site')
    .option('--content <dir>', 'Content directory', './content')
    .option('--output <dir>', 'Output directory', './dist')
    .option('--templates <dir>', 'Templates directory')
    .action((options) => {
    const contentDir = path_1.default.resolve(options.content);
    const outputDir = path_1.default.resolve(options.output);
    const templatesDir = options.templates ? path_1.default.resolve(options.templates) : undefined;
    (0, build_1.build)({ contentDir, outputDir, templatesDir });
});
program
    .command('serve')
    .description('Start a live-reload development server')
    .option('--content <dir>', 'Content directory', './content')
    .option('--output <dir>', 'Output directory', './dist')
    .option('--templates <dir>', 'Templates directory')
    .option('--port <number>', 'Port to listen on', '3000')
    .action((options) => {
    const contentDir = path_1.default.resolve(options.content);
    const outputDir = path_1.default.resolve(options.output);
    const templatesDir = options.templates ? path_1.default.resolve(options.templates) : undefined;
    const port = parseInt(options.port, 10);
    const instance = (0, serve_1.serve)({ contentDir, outputDir, templatesDir, port });
    instance.ready.then(() => {
        console.log(`Dev server running at http://localhost:${port}`);
    });
});
program.parse(process.argv);
