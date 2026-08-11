#!/usr/bin/env node
"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const commander_1 = require("commander");
const path_1 = __importDefault(require("path"));
const build_1 = require("./build");
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
    .action((options) => {
    const contentDir = path_1.default.resolve(options.content);
    const outputDir = path_1.default.resolve(options.output);
    (0, build_1.build)({ contentDir, outputDir });
});
program.parse(process.argv);
