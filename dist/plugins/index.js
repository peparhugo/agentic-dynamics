"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.DevServerPlugin = exports.TemplatePlugin = exports.MarkdownPlugin = exports.builtInPlugins = void 0;
const markdown_1 = require("./markdown");
const template_1 = require("./template");
const devserver_1 = require("./devserver");
exports.builtInPlugins = [
    markdown_1.MarkdownPlugin,
    template_1.TemplatePlugin,
    devserver_1.DevServerPlugin,
];
var markdown_2 = require("./markdown");
Object.defineProperty(exports, "MarkdownPlugin", { enumerable: true, get: function () { return markdown_2.MarkdownPlugin; } });
var template_2 = require("./template");
Object.defineProperty(exports, "TemplatePlugin", { enumerable: true, get: function () { return template_2.TemplatePlugin; } });
var devserver_2 = require("./devserver");
Object.defineProperty(exports, "DevServerPlugin", { enumerable: true, get: function () { return devserver_2.DevServerPlugin; } });
//# sourceMappingURL=index.js.map