"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.sortPages = exports.readPages = exports.findMarkdownFiles = exports.renderIndex = exports.renderPage = exports.DEFAULT_OUTPUT_DIR = exports.DEFAULT_CONTENT_DIR = void 0;
exports.buildSite = buildSite;
const engine_1 = require("./engine");
const template_1 = require("./template");
exports.DEFAULT_CONTENT_DIR = 'content';
exports.DEFAULT_OUTPUT_DIR = 'dist';
var template_2 = require("./template");
Object.defineProperty(exports, "renderPage", { enumerable: true, get: function () { return template_2.renderPage; } });
Object.defineProperty(exports, "renderIndex", { enumerable: true, get: function () { return template_2.renderIndex; } });
var markdown_1 = require("./markdown");
Object.defineProperty(exports, "findMarkdownFiles", { enumerable: true, get: function () { return markdown_1.findMarkdownFiles; } });
Object.defineProperty(exports, "readPages", { enumerable: true, get: function () { return markdown_1.readPages; } });
var engine_2 = require("./engine");
Object.defineProperty(exports, "sortPages", { enumerable: true, get: function () { return engine_2.sortPages; } });
function buildSite(contentDir, outputDir, templatesDir = template_1.DEFAULT_TEMPLATES_DIR) {
    const engine = new engine_1.SiteEngine({ contentDir, outputDir, templatesDir });
    return engine.build();
}
