import * as fs from 'fs';
import * as path from 'path';
import Handlebars from 'handlebars';
export class TemplateEngine {
    constructor(templatesDir) {
        this.cache = new Map();
        this.templatesDir = templatesDir;
        this.layoutsDir = path.join(templatesDir, 'layouts');
        this.partialsDir = path.join(templatesDir, 'partials');
        this.registerPartials();
    }
    registerPartials() {
        if (!fs.existsSync(this.partialsDir)) {
            return;
        }
        const partialFiles = fs.readdirSync(this.partialsDir).filter((f) => f.endsWith('.hbs'));
        for (const file of partialFiles) {
            const partialName = file.replace('.hbs', '');
            const partialContent = fs.readFileSync(path.join(this.partialsDir, file), 'utf-8');
            Handlebars.registerPartial(partialName, partialContent);
        }
    }
    getTemplate(templatePath) {
        if (this.cache.has(templatePath)) {
            return this.cache.get(templatePath);
        }
        const content = fs.readFileSync(templatePath, 'utf-8');
        const template = Handlebars.compile(content);
        this.cache.set(templatePath, template);
        return template;
    }
    renderTemplate(templatePath, data) {
        if (!fs.existsSync(templatePath)) {
            throw new Error(`Template not found: ${templatePath}`);
        }
        const template = this.getTemplate(templatePath);
        return template(data);
    }
    renderLayout(layoutName, data) {
        const layoutPath = path.join(this.layoutsDir, `${layoutName}.hbs`);
        return this.renderTemplate(layoutPath, data);
    }
    renderPageTemplate(templateName, data, layoutName) {
        const templatePath = path.join(this.templatesDir, `${templateName}.hbs`);
        let html = this.renderTemplate(templatePath, data);
        if (layoutName) {
            const layoutData = {
                ...data,
                body: html,
            };
            html = this.renderLayout(layoutName, layoutData);
        }
        return html;
    }
    getDefaultLayoutPath() {
        return path.join(this.layoutsDir, 'default.hbs');
    }
    hasLayout(layoutName) {
        const layoutPath = path.join(this.layoutsDir, `${layoutName}.hbs`);
        return fs.existsSync(layoutPath);
    }
    getAvailableTemplates() {
        if (!fs.existsSync(this.templatesDir)) {
            return [];
        }
        return fs
            .readdirSync(this.templatesDir)
            .filter((f) => f.endsWith('.hbs') && !fs.statSync(path.join(this.templatesDir, f)).isDirectory())
            .map((f) => f.replace('.hbs', ''));
    }
    getAvailableLayouts() {
        if (!fs.existsSync(this.layoutsDir)) {
            return [];
        }
        return fs
            .readdirSync(this.layoutsDir)
            .filter((f) => f.endsWith('.hbs'))
            .map((f) => f.replace('.hbs', ''));
    }
}
//# sourceMappingURL=template-engine.js.map