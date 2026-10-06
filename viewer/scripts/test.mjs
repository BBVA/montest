import { execFileSync } from "node:child_process";
import { readFileSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const fixtureDirectory = resolve(root, "..", "tests", "fixtures", "reports");
const names = ["sprt.jsonl", "nested-retry.jsonl", "incomplete.jsonl", "terminal-error.jsonl", "missing-sample.jsonl"];
const generated = join(root, "tests", "GeneratedFixtures.elm");
const escape = (source) => JSON.stringify(source);

// Format source tokens without parsing and rounding JSON numbers.
function formatJson(source) {
  const tokens = source.match(/"(?:\\.|[^"\\])*"|[{}\[\],:]|[^\s{}\[\],:]+/g);
  let depth = 0;
  let output = "";
  for (let index = 0; index < tokens.length; index++) {
    const token = tokens[index];
    const indent = () => "  ".repeat(depth);
    if (token === "{" || token === "[") {
      output += token;
      depth++;
      if (tokens[index + 1] !== "}" && tokens[index + 1] !== "]") output += "\n" + indent();
    } else if (token === "}" || token === "]") {
      depth--;
      if (tokens[index - 1] !== "{" && tokens[index - 1] !== "[") output += "\n" + indent();
      output += token;
    } else if (token === ",") output += ",\n" + indent();
    else if (token === ":") output += ": ";
    else output += token;
  }
  return output;
}
try {
  const entries = names.map((name) => [name, readFileSync(join(fixtureDirectory, name), "utf8")]);
  const formatted = entries.map(([name, contents]) => [name, contents.split("\n").filter(line => line.trim()).map(formatJson)]);
  writeFileSync(generated, `module GeneratedFixtures exposing (files, eventJson)\n\nfiles : List ( String, String )\nfiles =\n    [ ${entries.map(([name, contents]) => `( ${escape(name)}, ${escape(contents)} )`).join("\n    , ")}\n    ]\n\neventJson : List ( String, List String )\neventJson =\n    [ ${formatted.map(([name, events]) => `( ${escape(name)}, [ ${events.map(escape).join(", ")} ] )`).join("\n    , ")}\n    ]\n`);
  execFileSync(join(root, "node_modules", ".bin", "elm-test"), [], { cwd: root, stdio: "inherit" });
} finally { rmSync(generated, { force: true }); }
