import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, isAbsolute, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const compiler = process.env.ELM_COMPILER || join(root, "node_modules", ".bin", "elm");
if (process.env.ELM_COMPILER && !isAbsolute(compiler)) throw new Error("ELM_COMPILER must be an absolute path");
if (execFileSync(compiler, ["--version"], { encoding: "utf8" }).trim() !== "0.19.1") throw new Error("Elm compiler must report version 0.19.1");
const temporary = mkdtempSync(join(tmpdir(), "montest-viewer-"));
const output = join(temporary, "viewer.js");
const asset = resolve(root, "..", "src", "montest", "_assets", "viewer.js");
try {
  execFileSync(compiler, ["make", "src/Main.elm", "--optimize", `--output=${output}`], { cwd: root, stdio: "inherit" });
  const bytes = readFileSync(output);
  if (bytes.toString("utf8").toLowerCase().includes("</script")) throw new Error("Generated viewer bundle contains a closing script tag");
  if (process.argv.includes("--check")) {
    if (!bytes.equals(readFileSync(asset))) throw new Error("Committed viewer.js is stale; run npm run build");
  } else writeFileSync(asset, bytes);
} finally { rmSync(temporary, { recursive: true, force: true }); }
