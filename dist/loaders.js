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
exports.loadModule = loadModule;
const path_1 = __importDefault(require("path"));
const fs_1 = require("fs");
const module_1 = __importDefault(require("module"));
const url_1 = require("url");
const ModuleWithInternals = module_1.default;
const requireExtensions = require
    .extensions ?? {};
let typescript;
function getTypescript() {
    if (typescript === undefined) {
        try {
            // eslint-disable-next-line @typescript-eslint/no-var-requires
            typescript = require('typescript');
        }
        catch {
            typescript = null;
        }
    }
    return typescript ?? undefined;
}
let tsHookInstalled = false;
function ensureTsRequireHook() {
    if (tsHookInstalled) {
        return;
    }
    tsHookInstalled = true;
    const originalResolve = ModuleWithInternals._resolveFilename;
    const resolveCandidates = (request, parent) => {
        if (!request.startsWith('.') && !path_1.default.isAbsolute(request)) {
            return null;
        }
        const base = parent ? path_1.default.dirname(parent.filename) : process.cwd();
        const abs = path_1.default.resolve(base, request);
        const candidates = [
            abs,
            `${abs}.ts`,
            `${abs}.tsx`,
            `${abs}.mts`,
            `${abs}.js`,
            `${abs}.cjs`,
            `${abs}.json`,
            path_1.default.join(abs, 'index.ts'),
            path_1.default.join(abs, 'index.js'),
            path_1.default.join(abs, 'index.json'),
        ];
        for (const candidate of candidates) {
            if ((0, fs_1.existsSync)(candidate)) {
                return candidate;
            }
        }
        return null;
    };
    ModuleWithInternals._resolveFilename = function (request, parent, isMain, options) {
        const resolved = resolveCandidates(request, parent);
        if (resolved) {
            return resolved;
        }
        return originalResolve.call(this, request, parent, isMain, options);
    };
    const compile = (module, filename) => {
        const ts = getTypescript();
        if (!ts) {
            throw new Error('Loading a TypeScript config or plugin requires the "typescript" package to be installed.');
        }
        const source = (0, fs_1.readFileSync)(filename, 'utf8');
        const result = ts.transpileModule(source, {
            compilerOptions: {
                module: ts.ModuleKind.CommonJS,
                target: ts.ScriptTarget.ES2020,
                esModuleInterop: true,
                allowSyntheticDefaultImports: true,
                moduleResolution: ts.ModuleResolutionKind.NodeJs,
                skipLibCheck: true,
            },
            fileName: filename,
        });
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        module._compile(result.outputText, filename);
    };
    requireExtensions['.ts'] = compile;
    requireExtensions['.tsx'] = compile;
    requireExtensions['.mts'] = compile;
}
async function loadModule(filePath) {
    const ext = path_1.default.extname(filePath).toLowerCase();
    if (ext === '.mjs') {
        const mod = await Promise.resolve(`${(0, url_1.pathToFileURL)(filePath).href}`).then(s => __importStar(require(s)));
        return mod.default ?? mod;
    }
    if (ext === '.ts' || ext === '.tsx' || ext === '.mts') {
        ensureTsRequireHook();
    }
    if (ext === '.json') {
        return JSON.parse(await fs_1.promises.readFile(filePath, 'utf8'));
    }
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    return require(filePath);
}
//# sourceMappingURL=loaders.js.map