#!/usr/bin/env node
import fs from "node:fs/promises";
import { createRequire } from "node:module";
import path from "node:path";
import process from "node:process";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");

const ADMIN_HEADER = "X-PC1-Admin-Token";
const TOKEN_STORAGE_KEY = "pc1_admin_token";
const DEFAULT_OUTPUT_DIR = "testing/ui_gallery";
const DEFAULT_BASE_URL = "http://127.0.0.1:5173";
const DEFAULT_TIMEOUT_MS = 45_000;
const DEFAULT_VIEWPORT_WIDTH = 480;
const DEFAULT_VIEWPORT_HEIGHT = 1200;
const DEFAULT_MODULE_PREFIX = "UI TEST :: ";

function parseArgs(argv) {
  const args = {
    baseUrl: DEFAULT_BASE_URL,
    outputDir: DEFAULT_OUTPUT_DIR,
    timeoutMs: DEFAULT_TIMEOUT_MS,
    headful: false,
    adminToken: "",
    skipModuleSeeding: false,
    modulePrefix: DEFAULT_MODULE_PREFIX,
    viewportWidth: DEFAULT_VIEWPORT_WIDTH,
    viewportHeight: DEFAULT_VIEWPORT_HEIGHT,
  };

  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    const next = () => {
      if (i + 1 >= argv.length) {
        throw new Error(`Missing value for ${arg}`);
      }
      i += 1;
      return argv[i];
    };

    switch (arg) {
      case "--base-url":
        args.baseUrl = next();
        break;
      case "--output-dir":
        args.outputDir = next();
        break;
      case "--timeout-ms":
        args.timeoutMs = Number(next());
        break;
      case "--admin-token":
        args.adminToken = next();
        break;
      case "--module-prefix":
        args.modulePrefix = next();
        break;
      case "--viewport-width":
        args.viewportWidth = Number(next());
        break;
      case "--viewport-height":
        args.viewportHeight = Number(next());
        break;
      case "--headful":
        args.headful = true;
        break;
      case "--skip-module-seeding":
        args.skipModuleSeeding = true;
        break;
      default:
        throw new Error(`Unknown argument: ${arg}`);
    }
  }

  args.baseUrl = String(args.baseUrl || DEFAULT_BASE_URL).replace(/\/+$/, "");
  if (!Number.isFinite(args.timeoutMs) || args.timeoutMs < 1_000) {
    args.timeoutMs = DEFAULT_TIMEOUT_MS;
  }
  if (!Number.isFinite(args.viewportWidth) || args.viewportWidth < 240) {
    args.viewportWidth = DEFAULT_VIEWPORT_WIDTH;
  }
  if (!Number.isFinite(args.viewportHeight) || args.viewportHeight < 320) {
    args.viewportHeight = DEFAULT_VIEWPORT_HEIGHT;
  }
  if (!args.modulePrefix) {
    args.modulePrefix = DEFAULT_MODULE_PREFIX;
  }

  return args;
}

function sanitizeStem(name) {
  return String(name || "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
}

function stripAnsi(value) {
  return String(value || "").replace(/\u001b\[[0-9;]*m/g, "");
}

async function ensureFreshOutputDir(outputDir) {
  await fs.mkdir(outputDir, { recursive: true });
  const entries = await fs.readdir(outputDir, { withFileTypes: true });
  for (const entry of entries) {
    if (!entry.isFile()) continue;
    if (
      entry.name.endsWith(".png") ||
      entry.name.endsWith(".txt") ||
      entry.name.endsWith(".json")
    ) {
      await fs.rm(path.join(outputDir, entry.name), { force: true });
    }
  }
}

async function writeLines(filePath, lines) {
  const text = `${lines.join("\n")}${lines.length ? "\n" : ""}`;
  await fs.writeFile(filePath, text, "utf-8");
}

function configForType(typeId) {
  switch (typeId) {
    case "news":
      return { news_api_key: "" };
    case "rss":
      return { rss_feeds: [] };
    case "email":
      return {
        email_host: "imap.gmail.com",
        email_user: "",
        email_password: "",
        polling_interval: 60,
      };
    case "games":
    case "maze":
      return { difficulty: "Medium" };
    case "calendar":
      return { ical_sources: [], view_mode: "month" };
    case "webhook":
      return { url: "", method: "GET", headers: {}, json_path: "" };
    case "text":
      return {
        content_doc: { type: "doc", content: [{ type: "paragraph" }] },
      };
    case "qrcode":
      return { qr_type: "url", content: "https://example.com" };
    default:
      return {};
  }
}

function extractErrorDetail(status, json, text) {
  const detail =
    json?.detail || json?.message || json?.error || (text || "").slice(0, 120);
  return `HTTP ${status}${detail ? ` - ${detail}` : ""}`;
}

async function apiRequest(method, url, { token = "", data, expected = [200] } = {}) {
  const headers = { Accept: "application/json" };
  if (token) {
    headers[ADMIN_HEADER] = token;
  }
  let body;
  if (data !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(data);
  }

  const response = await fetch(url, { method, headers, body });
  const text = await response.text();
  let json = null;
  if (text) {
    try {
      json = JSON.parse(text);
    } catch {
      json = null;
    }
  }

  if (!expected.includes(response.status)) {
    throw new Error(`${method} ${url} failed: ${extractErrorDetail(response.status, json, text)}`);
  }

  return { status: response.status, json, text };
}

async function ensureAdminCompatibility(baseUrl, adminToken) {
  const auth = await apiRequest("GET", `${baseUrl}/api/system/auth/status`, {
    expected: [200],
  });

  if (auth.json?.token_required && !adminToken) {
    throw new Error(
      "Admin token is required by backend. Re-run with --admin-token <token>."
    );
  }
}

async function removeExistingSeedModules(baseUrl, adminToken, modulePrefix, notes) {
  const modulesRes = await apiRequest("GET", `${baseUrl}/api/modules`, {
    token: adminToken,
    expected: [200],
  });
  const modules = Object.values(modulesRes.json?.modules || {});
  const stale = modules.filter(
    (module) =>
      module &&
      typeof module.name === "string" &&
      module.name.startsWith(modulePrefix)
  );

  for (const module of stale) {
    try {
      await apiRequest("DELETE", `${baseUrl}/api/modules/${module.id}`, {
        token: adminToken,
        expected: [200, 404],
      });
      notes.push(`Removed stale seeded module: ${module.id}`);
    } catch (error) {
      notes.push(`Could not remove stale module ${module.id}: ${error.message}`);
    }
  }
}

async function seedModulePerType(baseUrl, adminToken, modulePrefix) {
  const typesRes = await apiRequest("GET", `${baseUrl}/api/module-types`, {
    expected: [200],
  });
  const moduleTypes = Array.isArray(typesRes.json?.moduleTypes)
    ? typesRes.json.moduleTypes
    : [];

  const stamp = Date.now();
  const createdModules = [];
  for (let i = 0; i < moduleTypes.length; i += 1) {
    const type = moduleTypes[i];
    const moduleId = `ui-test-${type.id}-${stamp}-${i}`;
    const payload = {
      id: moduleId,
      type: type.id,
      name: `${modulePrefix}${type.id.toUpperCase()}`,
      config: configForType(type.id),
    };

    const created = await apiRequest("POST", `${baseUrl}/api/modules`, {
      token: adminToken,
      data: payload,
      expected: [200],
    });

    createdModules.push({
      id: created.json?.module?.id || moduleId,
      name: created.json?.module?.name || payload.name,
      type: type.id,
      label: type.label || type.id,
    });
  }

  return { moduleTypes, createdModules };
}

async function cleanupCreatedModules(baseUrl, adminToken, createdModules, failures) {
  for (const module of [...createdModules].reverse()) {
    try {
      await apiRequest("DELETE", `${baseUrl}/api/modules/${module.id}`, {
        token: adminToken,
        expected: [200, 404],
      });
    } catch (error) {
      failures.push(`cleanup:${module.id}: ${error.message}`);
    }
  }
}

async function closeModal(page, timeoutMs) {
  const closeBtn = page.locator("button").filter({ hasText: "×" }).first();
  await closeBtn.waitFor({ state: "visible", timeout: timeoutMs });
  await closeBtn.click();
  await page.waitForTimeout(180);
}

async function clickTab(page, tabName, timeoutMs) {
  const tab = page.getByRole("tab", { name: tabName }).first();
  const fallbackButton = page.getByRole("button", { name: tabName }).first();
  const deadline = Date.now() + timeoutMs;

  if (await tab.isVisible().catch(() => false)) {
    await tab.click();
    await page.waitForTimeout(200);
    return;
  }
  if (await fallbackButton.isVisible().catch(() => false)) {
    await fallbackButton.click();
    await page.waitForTimeout(200);
    return;
  }

  while (Date.now() < deadline) {
    if (await tab.isVisible().catch(() => false)) {
      await tab.click();
      await page.waitForTimeout(200);
      return;
    }
    if (await fallbackButton.isVisible().catch(() => false)) {
      await fallbackButton.click();
      await page.waitForTimeout(200);
      return;
    }
    await page.waitForTimeout(250);
  }

  throw new Error(`Tab '${tabName}' not visible within timeout`);
}

async function withStep(state, stepName, fn) {
  console.log(`[settings-ui] step:start ${stepName}`);
  try {
    await fn();
    console.log(`[settings-ui] step:ok ${stepName}`);
  } catch (error) {
    state.failures.push(`${stepName}: ${stripAnsi(error.message)}`);
    console.log(`[settings-ui] step:fail ${stepName}`);
  }
}

async function capture(
  state,
  page,
  outputDir,
  stem,
  description,
  options = {}
) {
  state.captureIndex += 1;
  const fileName = `${String(state.captureIndex).padStart(2, "0")}_${sanitizeStem(stem)}.png`;
  const filePath = path.join(outputDir, fileName);
  const { locator = null, fullPage = true } = options;
  if (locator) {
    await locator.screenshot({ path: filePath });
  } else {
    await page.screenshot({ path: filePath, fullPage });
  }
  state.manifest.push(`${fileName}\t${description}`);
}

async function captureApWorkflow(state, page, args, outputDir) {
  await withStep(state, "ap_setup_screen", async () => {
    await page.getByRole("heading", { name: /WiFi Setup/i }).waitFor({
      state: "visible",
      timeout: args.timeoutMs,
    });
    await capture(state, page, outputDir, "wifi_setup", "WiFi setup screen (AP mode)");
  });

  await withStep(state, "ap_manual_entry", async () => {
    const manualEntry = page
      .getByRole("button", { name: /Enter network name manually/i })
      .first();
    await manualEntry.waitFor({ state: "visible", timeout: args.timeoutMs });
    await manualEntry.click();
    await capture(
      state,
      page,
      outputDir,
      "wifi_setup_manual_entry",
      "WiFi setup screen (manual SSID entry)"
    );
  });
}

async function captureClientWorkflow(state, page, args, outputDir, createdModules) {
  await withStep(state, "general_tab", async () => {
    await clickTab(page, "GENERAL", args.timeoutMs);
    await capture(state, page, outputDir, "general_tab", "General tab");
  });

  await withStep(state, "channels_tab", async () => {
    await clickTab(page, "CHANNELS", args.timeoutMs);
    await capture(state, page, outputDir, "channels_tab", "Channels tab");
  });

  await withStep(state, "schedule_modal", async () => {
    await clickTab(page, "CHANNELS", args.timeoutMs);
    const scheduleButton = page.locator('button[title="Configure Schedule"]').first();
    await scheduleButton.waitFor({ state: "visible", timeout: args.timeoutMs });
    await scheduleButton.click();
    await page.getByText(/Schedule Channel/i).first().waitFor({
      state: "visible",
      timeout: args.timeoutMs,
    });
    const scheduleModal = page
      .locator(".fixed.inset-0 .max-w-md")
      .filter({ hasText: "Schedule Channel" })
      .last();
    await capture(state, page, outputDir, "schedule_modal", "Schedule modal", {
      locator: scheduleModal,
      fullPage: false,
    });
    await closeModal(page, args.timeoutMs);
  });

  await withStep(state, "add_module_to_channel_modal", async () => {
    await clickTab(page, "CHANNELS", args.timeoutMs);
    const addButton = page
      .locator('button[title="Add a module to this channel"]')
      .first();
    await addButton.waitFor({ state: "visible", timeout: args.timeoutMs });
    await addButton.scrollIntoViewIfNeeded();
    await addButton.click();
    await page.getByText(/Add Module to Channel/i).first().waitFor({
      state: "visible",
      timeout: args.timeoutMs,
    });
    const addChannelModal = page
      .locator(".fixed.inset-0 .max-w-2xl")
      .filter({ hasText: "Add Module to Channel" })
      .last();
    await capture(
      state,
      page,
      outputDir,
      "add_module_modal_channel",
      "Add module modal (channel assignment)",
      { locator: addChannelModal, fullPage: false }
    );
    await closeModal(page, args.timeoutMs);
  });

  await withStep(state, "create_unassigned_modal", async () => {
    await clickTab(page, "CHANNELS", args.timeoutMs);
    const addUnassigned = page.locator('button[title="Add a new unassigned module"]');
    await addUnassigned.waitFor({ state: "visible", timeout: args.timeoutMs });
    await addUnassigned.scrollIntoViewIfNeeded();
    await addUnassigned.click();
    await page.getByText(/^Create Module$/).first().waitFor({
      state: "visible",
      timeout: args.timeoutMs,
    });
    const addUnassignedModal = page
      .locator(".fixed.inset-0 .max-w-2xl")
      .filter({ hasText: "Create Module" })
      .last();
    await capture(
      state,
      page,
      outputDir,
      "add_module_modal_unassigned",
      "Create module modal (unassigned)",
      { locator: addUnassignedModal, fullPage: false }
    );
    await closeModal(page, args.timeoutMs);
  });

  const sortedModules = [...createdModules].sort((a, b) =>
    a.type.localeCompare(b.type)
  );
  for (const module of sortedModules) {
    await withStep(state, `edit_module_${module.type}`, async () => {
      await clickTab(page, "CHANNELS", args.timeoutMs);
      const card = page
        .locator('[data-dnd-item="true"]')
        .filter({ hasText: module.name })
        .first();
      await card.waitFor({ state: "visible", timeout: args.timeoutMs });
      await card.scrollIntoViewIfNeeded();
      await card.click();
      await page.getByText(/^Edit Module$/).first().waitFor({
        state: "visible",
        timeout: args.timeoutMs,
      });
      await page.waitForTimeout(160);
      const editModal = page
        .locator(".fixed.inset-0 .max-w-2xl")
        .filter({ hasText: "Edit Module" })
        .last();
      await capture(
        state,
        page,
        outputDir,
        `edit_module_${module.type}`,
        `Edit module modal (${module.type})`,
        { locator: editModal, fullPage: false }
      );
      await closeModal(page, args.timeoutMs);
    });
  }
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const outputDir = path.resolve(args.outputDir);
  await ensureFreshOutputDir(outputDir);
  console.log(`[settings-ui] output_dir=${outputDir}`);

  const state = {
    captureIndex: 0,
    manifest: [],
    failures: [],
    warnings: [],
  };
  const notes = [];

  let createdModules = [];
  let browser = null;
  try {
    console.log("[settings-ui] checking auth compatibility");
    await ensureAdminCompatibility(args.baseUrl, args.adminToken);

    console.log("[settings-ui] fetching wifi status");
    const wifi = await apiRequest("GET", `${args.baseUrl}/api/wifi/status`, {
      expected: [200],
    });
    const wifiMode = wifi.json?.mode || "unknown";
    notes.push(`wifi_mode=${wifiMode}`);

    if (!args.skipModuleSeeding && wifiMode !== "ap") {
      console.log("[settings-ui] seeding module instances for editor captures");
      await removeExistingSeedModules(
        args.baseUrl,
        args.adminToken,
        args.modulePrefix,
        notes
      );
      const seeded = await seedModulePerType(
        args.baseUrl,
        args.adminToken,
        args.modulePrefix
      );
      createdModules = seeded.createdModules;
      notes.push(`seeded_modules=${createdModules.length}`);
      console.log(`[settings-ui] seeded_modules=${createdModules.length}`);
    } else if (args.skipModuleSeeding) {
      notes.push("module_seeding=skipped_by_flag");
    } else {
      notes.push("module_seeding=skipped_ap_mode");
    }

    console.log("[settings-ui] launching browser");
    browser = await chromium.launch({ headless: !args.headful });
    const context = await browser.newContext({
      viewport: { width: args.viewportWidth, height: args.viewportHeight },
    });

    if (args.adminToken) {
      await context.addInitScript(
        (token, key) => window.localStorage.setItem(key, token),
        args.adminToken,
        TOKEN_STORAGE_KEY
      );
    }

    const page = await context.newPage();

    page.on("dialog", async (dialog) => {
      if (dialog.type() === "prompt" && args.adminToken) {
        await dialog.accept(args.adminToken);
      } else if (dialog.type() === "confirm") {
        await dialog.accept();
      } else {
        await dialog.dismiss();
      }
      state.warnings.push(`dialog:${dialog.type()}:${dialog.message()}`);
    });
    page.on("pageerror", (error) => {
      state.warnings.push(`pageerror:${error.message}`);
    });
    page.on("console", (msg) => {
      const type = msg.type();
      if (type === "error" || type === "warning") {
        state.warnings.push(`console.${type}:${msg.text()}`);
      }
    });

    await page.goto(args.baseUrl, {
      waitUntil: "domcontentloaded",
      timeout: args.timeoutMs,
    });
    console.log("[settings-ui] page loaded");
    await page.waitForTimeout(600);

    const isSettingsUi = await page
      .locator("h1", { hasText: "PC-1 SETTINGS" })
      .first()
      .isVisible()
      .catch(() => false);
    const isApUi = await page
      .getByRole("heading", { name: /WiFi Setup/i })
      .first()
      .isVisible()
      .catch(() => false);

    if (isApUi && !isSettingsUi) {
      await captureApWorkflow(state, page, args, outputDir);
    } else {
      await captureClientWorkflow(state, page, args, outputDir, createdModules);
    }

    await context.close();
  } catch (error) {
    state.failures.push(`fatal:${stripAnsi(error.message)}`);
  } finally {
    if (browser) {
      await browser.close();
    }
    await cleanupCreatedModules(
      args.baseUrl,
      args.adminToken,
      createdModules,
      state.failures
    );
  }

  await writeLines(path.join(outputDir, "manifest.txt"), state.manifest);
  await writeLines(
    path.join(outputDir, "failures.txt"),
    state.failures.length ? state.failures : ["OK"]
  );
  await writeLines(path.join(outputDir, "notes.txt"), notes);
  if (state.warnings.length) {
    await writeLines(path.join(outputDir, "runtime_warnings.txt"), state.warnings);
  }

  console.log(
    `[settings-ui] wrote ${state.manifest.length} screenshots to ${outputDir}`
  );
  if (state.failures.length) {
    console.error(
      `[settings-ui] completed with ${state.failures.length} failures. See failures.txt`
    );
    return 1;
  }
  return 0;
}

main()
  .then((code) => {
    process.exit(code);
  })
  .catch((error) => {
    console.error(`[settings-ui] fatal: ${error.message}`);
    process.exit(1);
  });
