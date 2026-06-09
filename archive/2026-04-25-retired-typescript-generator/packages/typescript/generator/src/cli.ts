#!/usr/bin/env node
import path from "node:path";

import { generateTypeScriptProject, readServiceDefinition } from "./generator.js";

function parseArgs(argv: string[]) {
  const args = new Map<string, string | boolean>();
  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    if (!token.startsWith("--")) continue;
    const key = token.slice(2);
    if (key === "force") {
      args.set(key, true);
      continue;
    }
    const value = argv[index + 1];
    if (!value || value.startsWith("--")) {
      throw new Error(`Missing value for --${key}`);
    }
    args.set(key, value);
    index += 1;
  }
  return args;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const definitionPath = String(args.get("definition") ?? "");
  const outputDir = String(args.get("output") ?? "");
  const packageName = String(args.get("package-name") ?? "").trim() || undefined;
  const dependencySourceRaw = String(args.get("dependency-source") ?? "registry");

  if (!definitionPath || !outputDir) {
    throw new Error("Usage: anip-generate-typescript --definition <path> --output <dir> [--package-name <name>] [--dependency-source registry|local] [--force]");
  }
  if (dependencySourceRaw !== "registry" && dependencySourceRaw !== "local") {
    throw new Error(`Unsupported --dependency-source ${dependencySourceRaw}. Expected registry or local.`);
  }

  const definition = await readServiceDefinition(path.resolve(definitionPath));
  const project = await generateTypeScriptProject(definition, {
    outputDir: path.resolve(outputDir),
    packageName,
    dependencySource: dependencySourceRaw,
    force: Boolean(args.get("force")),
  });

  process.stdout.write(
    JSON.stringify(
      {
        status: "ok",
        system_name: project.systemName,
        package_name: project.packageName,
        output_dir: path.resolve(outputDir),
        file_count: project.files.length,
      },
      null,
      2,
    ) + "\n",
  );
}

main().catch((error) => {
  const message = error instanceof Error ? error.message : String(error);
  process.stderr.write(`${message}\n`);
  process.exitCode = 1;
});
