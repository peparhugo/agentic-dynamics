"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.SsgEngine = void 0;
const fs = __importStar(require("fs"));
const path = __importStar(require("path"));
const config_1 = require("./config");
const markdown_plugin_1 = require("../plugins/markdown-plugin");
const template_plugin_1 = require("../plugins/template-plugin");
function getDefaultPlugins() {
    return [
        new markdown_plugin_1.MarkdownPlugin(),
        new template_plugin_1.TemplatePlugin(),
    ];
}
class SsgEngine {
    constructor(additionalPlugins) {
        const config = (0, config_1.loadConfig)();
        const configPlugins = config.plugins || [];
        if (configPlugins.length > 0) {
            this.plugins = [...configPlugins, ...(additionalPlugins || [])];
        }
        else {
            this.plugins = [...getDefaultPlugins(), ...(additionalPlugins || [])];
        }
    }
    build(contentDir, outputDir, templatesDir) {
        const absoluteContent = path.resolve(contentDir);
        if (!fs.existsSync(absoluteContent)) {
            throw new Error(`Content directory does not exist: ${absoluteContent}`);
        }
        const ctx = {
            contentDir: absoluteContent,
            outputDir,
            templatesDir,
        };
        for (const plugin of this.plugins) {
            if (plugin.setContext)
                plugin.setContext(ctx);
        }
        for (const plugin of this.plugins) {
            if (plugin.onStart)
                plugin.onStart();
        }
        const files = fs.readdirSync(absoluteContent).filter((f) => f.endsWith('.md'));
        const pages = files.map((file) => ({
            slug: path.basename(file, '.md'),
            title: path.basename(file, '.md'),
            content: fs.readFileSync(path.join(absoluteContent, file), 'utf-8'),
            html: '',
        }));
        for (const plugin of this.plugins) {
            if (plugin.beforeBuild)
                plugin.beforeBuild();
        }
        for (const page of pages) {
            for (const plugin of this.plugins) {
                if (plugin.onFile)
                    plugin.onFile(page);
            }
        }
        pages.sort((a, b) => {
            if (a.date && b.date) {
                return b.date.localeCompare(a.date);
            }
            if (a.date)
                return -1;
            if (b.date)
                return 1;
            return a.title.localeCompare(b.title);
        });
        for (const plugin of this.plugins) {
            if (plugin.afterBuild)
                plugin.afterBuild(pages);
        }
        for (const plugin of this.plugins) {
            if (plugin.onEnd)
                plugin.onEnd();
        }
    }
}
exports.SsgEngine = SsgEngine;
//# sourceMappingURL=engine.js.map