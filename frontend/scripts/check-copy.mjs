#!/usr/bin/env node
// Fails the build if any UI string promises results ("guaranteed", "go viral",
// "overnight", "100%"...). Rules live in shared/copy-rules.json and are shared
// with the API test suite. Class names, styles and SVG geometry are skipped so
// only words a person could read are checked.
import { readFileSync, readdirSync, statSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";
import ts from "typescript";

const here = dirname(fileURLToPath(import.meta.url));
const web = join(here, "..");
const root = join(web, "..");
const rules = JSON.parse(readFileSync(join(root, "shared", "copy-rules.json"), "utf8")).banned.map((r) => ({
  rx: new RegExp(r.pattern, "i"),
  why: r.why,
}));

const SKIP_ATTRS = new Set([
  "className", "class", "style", "d", "viewBox", "fill", "stroke", "width", "height", "x", "y", "cx", "cy", "r",
  "offset", "stopColor", "points", "transform", "href", "to", "src", "id", "key", "type", "role", "dataKey",
  "strokeWidth", "strokeDasharray", "gradientTransform", "x1", "x2", "y1", "y2", "rel", "target",
]);
const SKIP_CALLS = new Set(["cn", "cva", "clsx", "twMerge", "require", "import", "querySelector", "matchMedia"]);
const CSS_PROPS = /^(width|height|min|max|top|left|right|bottom|inset|margin|padding|background|transform|transition|opacity|color|border|font|grid|flex|gap|filter|boxShadow|zIndex)/;

function* walk(dir) {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) yield* walk(p);
    else if (/\.(tsx?|mts)$/.test(name)) yield p;
  }
}

function skipped(node) {
  for (let p = node.parent; p; p = p.parent) {
    if (ts.isJsxAttribute(p)) return SKIP_ATTRS.has(p.name.getText());
    if (ts.isCallExpression(p)) {
      const callee = p.expression.getText();
      if (SKIP_CALLS.has(callee.split(".").pop())) return true;
    }
    if (ts.isPropertyAssignment(p) && node.parent === p && CSS_PROPS.test(p.name.getText())) return true;
    if (ts.isImportDeclaration(p) || ts.isExportDeclaration(p)) return true;
    if (ts.isJsxElement(p) || ts.isJsxSelfClosingElement(p)) return false;
  }
  return false;
}

const problems = [];
let checked = 0;
for (const file of walk(join(web, "src"))) {
  const text = readFileSync(file, "utf8");
  const sf = ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true, file.endsWith("x") ? ts.ScriptKind.TSX : ts.ScriptKind.TS);
  const visit = (node) => {
    let value = null;
    if (ts.isJsxText(node)) value = node.getText();
    else if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) value = node.text;
    else if (ts.isTemplateHead(node) || ts.isTemplateMiddle(node) || ts.isTemplateTail(node)) value = node.text;
    if (value && value.trim() && !skipped(node)) {
      checked++;
      for (const r of rules) {
        if (r.rx.test(value)) {
          const { line } = sf.getLineAndCharacterOfPosition(node.getStart());
          problems.push(`${relative(root, file)}:${line + 1}  "${value.trim().slice(0, 70)}"  (${r.why})`);
        }
      }
    }
    ts.forEachChild(node, visit);
  };
  visit(sf);
}

if (problems.length) {
  console.error(`Copy rules failed. JodiDar AI never promises results:\n\n${problems.join("\n")}\n`);
  process.exit(1);
}
console.log(`Copy rules passed (${checked} UI strings checked, no promises found).`);
