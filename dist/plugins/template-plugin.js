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
exports.TemplatePlugin = void 0;
const fs = __importStar(require("fs"));
const path = __importStar(require("path"));
const template_engine_1 = require("../src/template-engine");
const template_1 = require("../src/template");
class TemplatePlugin {
    constructor() {
        this.name = 'template';
        this.context = null;
    }
    setContext(context) {
        this.context = context;
    }
    afterBuild(pages) {
        const ctx = this.context;
        if (!ctx)
            return;
        const { outputDir, templatesDir, skippedSlugs } = ctx;
        let engine;
        if (templatesDir && fs.existsSync(templatesDir)) {
            engine = new template_engine_1.TemplateEngine({ templatesDir: path.resolve(templatesDir) });
        }
        const absoluteOutput = path.resolve(outputDir);
        if (!fs.existsSync(absoluteOutput)) {
            fs.mkdirSync(absoluteOutput, { recursive: true });
        }
        for (const page of pages) {
            if (skippedSlugs?.has(page.slug)) {
                continue;
            }
            let html;
            if (engine) {
                const tplName = page.template || (engine.hasTemplate('default') ? 'default' : undefined);
                const lytName = page.layout || (engine.hasLayout('default') ? 'default' : undefined);
                html = engine.render(page, tplName, lytName);
            }
            else {
                html = (0, template_1.pageTemplate)(page);
            }
            fs.writeFileSync(path.join(absoluteOutput, `${page.slug}.html`), html);
            page.html = html;
        }
        let indexHtml;
        if (engine && engine.hasIndex()) {
            indexHtml = engine.renderIndex(pages);
        }
        else {
            indexHtml = (0, template_1.indexTemplate)(pages);
        }
        fs.writeFileSync(path.join(absoluteOutput, 'index.html'), indexHtml);
    }
}
exports.TemplatePlugin = TemplatePlugin;
//# sourceMappingURL=template-plugin.js.map