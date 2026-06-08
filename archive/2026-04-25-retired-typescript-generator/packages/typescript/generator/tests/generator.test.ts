import { mkdtemp, readFile, rm } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import { buildTypeScriptProject, generateTypeScriptProject, readServiceDefinition } from "../src/index.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const fixturePath = path.join(__dirname, "fixtures", "work-item-fronting-definition.json");

describe("@anip-dev/generator-typescript", () => {
  it("builds a runnable project file set from a service definition", async () => {
    const definition = await readServiceDefinition(fixturePath);
    const generated = buildTypeScriptProject(definition, {
      dependencySource: "registry",
      httpRuntime: "hono",
      port: 4100,
    });

    expect(generated.packageName).toBe("work-item-governance-service");
    expect(generated.files.some((file) => file.path === "src/app.ts")).toBe(true);
    expect(generated.files.some((file) => file.path === "src/generated/capabilities.ts")).toBe(true);
    expect(generated.files.some((file) => file.path === "tests/service-smoke.test.ts")).toBe(true);

    const capabilityModule = generated.files.find((file) => file.path === "src/generated/capabilities.ts");
    const runtimeTargetModule = generated.files.find((file) => file.path === "src/generated/runtime-target.ts");
    const adapterModule = generated.files.find((file) => file.path === "src/runtime/backend-adapter.ts");
    expect(capabilityModule?.content).toContain("Generated host prepared a governed preview");
    expect(capabilityModule?.content).toContain("if (!configured) return capability.backend_bindings[0];");
    expect(runtimeTargetModule?.content).toContain("export type GeneratedCapabilityInputMetadata");
    expect(runtimeTargetModule?.content).toContain("[key: string]: unknown");
    expect(adapterModule?.content).toContain("createDefaultBackendAdapter");
  });

  it("emits local file dependencies when requested", async () => {
    const definition = await readServiceDefinition(fixturePath);
    const generated = buildTypeScriptProject(definition, {
      dependencySource: "local",
      httpRuntime: "hono",
      port: 4100,
    });

    const packageJson = JSON.parse(
      generated.files.find((file) => file.path === "package.json")?.content || "{}",
    ) as { dependencies?: Record<string, string> };

    expect(packageJson.dependencies?.["@anip-dev/service"]).toContain("file:");
    expect(packageJson.dependencies?.["@anip-dev/hono"]).toContain("file:");
    expect(packageJson.dependencies?.hono).toContain("file:");
    expect(packageJson.dependencies?.["@hono/node-server"]).toContain("file:");
  });

  it("writes the generated project to disk", async () => {
    const definition = await readServiceDefinition(fixturePath);
    const outputDir = await mkdtemp(path.join(os.tmpdir(), "anip-generator-"));

    try {
      await generateTypeScriptProject(definition, {
        outputDir,
        force: true,
      });

      const packageJson = JSON.parse(await readFile(path.join(outputDir, "package.json"), "utf8")) as { name: string };
      const runtimeTarget = await readFile(path.join(outputDir, "src/generated/runtime-target.ts"), "utf8");
      expect(packageJson.name).toBe("work-item-governance-service");
      expect(runtimeTarget).toContain("work_item.prepare_update");
      expect(runtimeTarget).toContain("\"backend_input_mode\": \"hybrid\"");
    } finally {
      await rm(outputDir, { recursive: true, force: true });
    }
  });
});
