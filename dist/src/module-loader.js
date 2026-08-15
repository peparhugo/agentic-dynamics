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
exports.loadTsModule = loadTsModule;
const fs = __importStar(require("fs"));
const path = __importStar(require("path"));
const typescript_1 = __importDefault(require("typescript"));
/**
 * Load a TypeScript module by transpiling it to CommonJS in memory and
 * evaluating it. Returns the module's default export (or the module itself
 * when there is no default export).
 *
 * This is used to load `ssg.config.ts` and plugin modules from `./plugins/`
 * without requiring a registered transpiler hook.
 */
function loadTsModule(filePath) {
    const source = fs.readFileSync(filePath, 'utf8');
    const compiled = typescript_1.default.transpileModule(source, {
        compilerOptions: {
            module: typescript_1.default.ModuleKind.CommonJS,
            target: typescript_1.default.ScriptTarget.ES2020,
            esModuleInterop: true,
        },
        fileName: filePath,
    }).outputText;
    const moduleObj = { exports: {} };
    const dir = path.dirname(filePath);
    const baseRequire = require;
    const localRequire = (id) => {
        if (id.startsWith('.') || id.startsWith('/')) {
            return loadTsModule(path.resolve(dir, id));
        }
        try {
            return baseRequire(id);
        }
        catch (err) {
            try {
                return baseRequire(require.resolve(id, { paths: [dir] }));
            }
            catch {
                throw err;
            }
        }
    };
    const factory = new Function('module', 'exports', 'require', '__filename', '__dirname', compiled);
    factory(moduleObj, moduleObj.exports, localRequire, filePath, dir);
    const loaded = moduleObj.exports.default ?? moduleObj.exports;
    return loaded;
}
