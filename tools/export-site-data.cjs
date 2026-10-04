// Dumps the portfolio's data files (src/data/*.ts) as JSON for build_readme.py.
// Usage: node tools/export-site-data.cjs <path-to-portfolio> > tools/site-data.json
const fs = require("fs");
const path = require("path");
const root = process.argv[2] || path.join(__dirname, "..", "..", "portfolio");
const ts = require(path.join(root, "node_modules", "typescript"));
const out = {};
for (const name of ["experience", "projects", "research"]) {
  const src = fs.readFileSync(path.join(root, "src", "data", `${name}.ts`), "utf8");
  const js = ts.transpileModule(src, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText;
  const mod = { exports: {} };
  new Function("module", "exports", "require", js)(mod, mod.exports, require);
  Object.assign(out, mod.exports);
}
process.stdout.write(JSON.stringify(out, null, 2));
