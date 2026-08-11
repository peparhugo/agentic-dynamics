#!/usr/bin/env node
"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const path_1 = __importDefault(require("path"));
const engine_1 = require("./engine");
const markdown_1 = require("./plugins/markdown");
const template_1 = require("./plugins/template");
const devserver_1 = require("./plugins/devserver");
function getDefaultPlugins() {
    return [
        new markdown_1.MarkdownPlugin(),
        new template_1.TemplatePlugin(),
        new devserver_1.DevServerPlugin(),
    ];
}
function loadConfigPlugins(cwd) {
    try {
        const configPath = path_1.default.resolve(cwd, 'ssg.config.js');
        const config = require(configPath);
        if (config && Array.isArray(config.plugins)) {
            return config.plugins;
        }
        if (config && config.default && Array.isArray(config.default.plugins)) {
            return config.default.plugins;
        }
    }
    catch {
        // config file not found or invalid, use defaults
    }
    return getDefaultPlugins();
}
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
async function main() {
    if (command === 'build') {
        const { content, output, templates } = parseArgs(process.argv.slice(3));
        const plugins = loadConfigPlugins(process.cwd());
        const engine = new engine_1.SSGEngine({ content, output, templates, port: 3000 });
        for (const plugin of plugins) {
            engine.register(plugin);
        }
        await engine.build();
        console.log(`Site generated in ${output} (${engine.pages.length} pages)`);
    }
    else if (command === 'serve') {
        const { content, output, templates, port } = parseArgs(process.argv.slice(3));
        const plugins = loadConfigPlugins(process.cwd());
        const engine = new engine_1.SSGEngine({ content, output, templates, port });
        for (const plugin of plugins) {
            engine.register(plugin);
        }
        const pages = engine.pages;
        await engine.build();
        console.log(`Site generated in ${output} (${pages.length} pages)`);
        await engine.serve();
    }
    else {
        console.log('Usage: npx ssg build [--content <dir>] [--output <dir>] [--templates <dir>]\n' +
            '       npx ssg serve [--content <dir>] [--output <dir>] [--templates <dir>] [--port <port>]');
        process.exit(command ? 1 : 0);
    }
}
main().catch((err) => {
    console.error(err);
    process.exit(1);
});
//# sourceMappingURL=cli.js.map