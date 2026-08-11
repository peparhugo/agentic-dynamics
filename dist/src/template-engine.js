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
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.TemplateEngine = void 0;
const fs = __importStar(require("fs"));
const path = __importStar(require("path"));
const handlebars_1 = __importDefault(require("handlebars"));
class TemplateEngine {
    constructor(options) {
        this.templatesDir = options.templatesDir;
        this.layoutsDir = path.join(this.templatesDir, 'layouts');
        this.partialsDir = path.join(this.templatesDir, 'partials');
        this.compiledTemplates = new Map();
        this.compiledLayouts = new Map();
        this.loadPartials();
    }
    loadPartials() {
        if (!fs.existsSync(this.partialsDir))
            return;
        const files = fs.readdirSync(this.partialsDir).filter((f) => f.endsWith('.hbs'));
        for (const file of files) {
            const name = path.basename(file, '.hbs');
            const source = fs.readFileSync(path.join(this.partialsDir, file), 'utf-8');
            handlebars_1.default.registerPartial(name, source);
        }
    }
    loadTemplate(name) {
        const filePath = path.join(this.templatesDir, `${name}.hbs`);
        if (!fs.existsSync(filePath)) {
            throw new Error(`Template not found: ${filePath}`);
        }
        const source = fs.readFileSync(filePath, 'utf-8');
        return handlebars_1.default.compile(source);
    }
    loadLayout(name) {
        const filePath = path.join(this.layoutsDir, `${name}.hbs`);
        if (!fs.existsSync(filePath)) {
            throw new Error(`Layout not found: ${filePath}`);
        }
        const source = fs.readFileSync(filePath, 'utf-8');
        return handlebars_1.default.compile(source);
    }
    getTemplate(name) {
        if (!this.compiledTemplates.has(name)) {
            this.compiledTemplates.set(name, this.loadTemplate(name));
        }
        return this.compiledTemplates.get(name);
    }
    getLayout(name) {
        if (!this.compiledLayouts.has(name)) {
            this.compiledLayouts.set(name, this.loadLayout(name));
        }
        return this.compiledLayouts.get(name);
    }
    hasTemplate(name) {
        return fs.existsSync(path.join(this.templatesDir, `${name}.hbs`));
    }
    hasLayout(name) {
        return fs.existsSync(path.join(this.layoutsDir, `${name}.hbs`));
    }
    hasIndex() {
        return fs.existsSync(path.join(this.templatesDir, 'index.hbs'));
    }
    render(page, templateName, layoutName) {
        const tplName = templateName || 'default';
        const template = this.getTemplate(tplName);
        const templateHtml = template(page);
        const lytName = layoutName || 'default';
        if (this.hasLayout(lytName)) {
            const layout = this.getLayout(lytName);
            return layout({ ...page, body: templateHtml });
        }
        return templateHtml;
    }
    renderIndex(pages) {
        const template = this.getTemplate('index');
        return template({ pages });
    }
}
exports.TemplateEngine = TemplateEngine;
//# sourceMappingURL=template-engine.js.map