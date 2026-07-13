// After-deploy verification script for xiangmushu design-system rollout.
// Usage:
//   1. SSH to server and run:  cd /root/h/xiangmushu && git pull origin master && cd frontend && npm run build
//   2. Wait ~5 seconds for the service to reload the new assets
//   3. Run this script from any machine with Node + Playwright installed:
//        node verify-after-deploy.cjs
//      (optional) BASE=http://my-staging.example.com node verify-after-deploy.cjs
//
// The script asserts that production is serving the NEW build (post commit c331a8c)
// and that all design-system fixes from this session's red / yellow / green
// consolidations are actually present in the rendered HTML.

const { chromium } = require("playwright");

const BASE = process.env.BASE || "http://118.126.102.143";
const TIMEOUT_MS = 30_000;

let passed = 0;
let failed = 0;
const failures = [];

function ok(name, detail) {
  passed++;
  console.log(`  \u2713  ${name}${detail ? "  (" + detail + ")" : ""}`);
}
function fail(name, detail) {
  failed++;
  failures.push({ name, detail });
  console.log(`  \u2717  ${name}  ${detail ? "  (" + detail + ")" : ""}`);
}

// Old build fingerprint we definitely do NOT want to see after deploy.
const OLD_HASHES = ["CWR_6Ju2", "DgpNz0RN", "DKYs-LEY", "DRU1ALYo", "EkQ7gk5U"];
const EXPECTED_TITLE_ZH = "\u9879\u76ee\u4e66\u5de5\u4f5c\u53f0"; // 项目书工作台

(async () => {
  console.log(`\n\u25b6  Verifying ${BASE}\n`);

  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({
    viewport: { width: 1280, height: 900 },
    locale: "zh-CN",
  });
  ctx.setDefaultTimeout(TIMEOUT_MS);
  const page = await ctx.newPage();

  // ──────────────────────────────────────────────
  // 1. Build fingerprint must be NEW
  // ──────────────────────────────────────────────
  console.log("[1] Build fingerprint");
  await page.goto(BASE + "/auth", { waitUntil: "networkidle" });
  const buildHash = await page.evaluate(() => {
    for (const link of document.querySelectorAll('link[rel="stylesheet"]')) {
      const m = link.href.match(/index-([^./\\]+)\.css/);
      if (m) return m[1];
    }
    for (const s of document.querySelectorAll('script[src]')) {
      const m = s.src.match(/index-([^./\\]+)\.js/);
      if (m) return m[1];
    }
    return null;
  });
  if (!buildHash) {
    fail("build hash readable", "no index-*.css / index-*.js found");
  } else if (OLD_HASHES.some((h) => buildHash.includes(h))) {
    fail("build hash is new", `still on OLD hash ${buildHash} — run 'git pull && npm run build' on server`);
  } else {
    ok("build hash is new", buildHash);
  }

  // ──────────────────────────────────────────────
  // 2. Page title: 项目书工作台 (renamed from 智能生成舱)
  // ──────────────────────────────────────────────
  console.log("\n[2] Document title & meta");
  const title = await page.title();
  if (title.includes("\u667a\u80fd\u751f\u6210\u8231")) {
    fail("title renamed", `still old: "${title}"`);
  } else if (title === EXPECTED_TITLE_ZH) {
    ok("title renamed", title);
  } else {
    // Acceptable: may contain prefix/suffix but not the old name.
    fail("title matches 项目书工作台", `got: "${title}"`);
  }

  const lang = await page.evaluate(() => document.documentElement.lang);
  if (lang === "zh-CN") ok("<html lang> (zh)", lang);
  else fail("<html lang> (zh)", `got "${lang}"`);

  // ──────────────────────────────────────────────
  // 3. Old-name residue (生成舱 → 生成工作台)
  // ──────────────────────────────────────────────
  console.log("\n[3] Naming migration (生成舱 → 生成工作台)");
  await page.goto(BASE + "/auth"); // ensure we're not authenticated
  await page.goto(BASE + "/");
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(800);
  const hasOldName = await page.evaluate(() => document.body.innerText.includes("\u751f\u6210\u8231"));
  const hasNewName = await page.evaluate(() => document.body.innerText.includes("\u751f\u6210\u5de5\u4f5c\u53f0"));
  if (hasOldName) fail("legacy name removed", "still contains 生成舱");
  else ok("legacy name removed");
  if (hasNewName) ok("new name present", "生成工作台");
  else fail("new name present", "生成工作台 not found in DOM");

  // Note: if the user is unauthenticated we get redirected to /auth, so
  // the above may find nothing. Re-check on /auth too.
  await page.goto(BASE + "/auth", { waitUntil: "networkidle" });
  const authHasOld = await page.evaluate(() => document.body.innerText.includes("\u751f\u6210\u8231"));
  if (authHasOld) fail("login page uses new name", "still shows 生成舱");

  // ──────────────────────────────────────────────
  // 4. Red-priority violations removed
  // ──────────────────────────────────────────────
  console.log("\n[4] Red-priority violation removal");
  const redCheck = await page.evaluate(() => {
    const all = [...document.querySelectorAll("*")];
    const classTextOf = (el) => (el.getAttribute("class") || "");
    return {
      backdropBlur2xl: all.some((el) => classTextOf(el).includes("backdrop-blur-2xl")),
      roundedLg: all.some((el) => classTextOf(el).includes("rounded-lg")),
      night950Opacity: all.filter((el) =>
        /bg-night-950\/[0-9]/.test(classTextOf(el))
      ).length,
      white035: all.filter((el) =>
        /bg-white\/\[0\.03[05]?\]/.test(classTextOf(el))
      ).length,
    };
  });
  if (redCheck.backdropBlur2xl) fail("backdrop-blur-2xl removed", "still in DOM");
  else ok("backdrop-blur-2xl removed");
  if (redCheck.roundedLg) fail("rounded-lg removed", "still in DOM");
  else ok("rounded-lg removed");
  if (redCheck.night950Opacity > 0) fail("bg-night-950/* opacities consolidated", `${redCheck.night950Opacity} remaining`);
  else ok("bg-night-950/* opacities consolidated");
  if (redCheck.white035 > 0) fail("bg-white/[0.035] / [0.03] consolidated", `${redCheck.white035} remaining`);
  else ok("bg-white/[0.035] / [0.03] consolidated");

  // ──────────────────────────────────────────────
  // 5. Accessibility additions
  // ──────────────────────────────────────────────
  console.log("\n[5] Accessibility");
  const a11y = await page.evaluate(() => ({
    skipLink: !!document.querySelector('a[href="#main-content"]'),
    ariaHiddenCount: document.querySelectorAll('[aria-hidden="true"]').length,
    svgCount: document.querySelectorAll("svg").length,
    tabularNumsCount: (() => {
      let n = 0;
      document.querySelectorAll("*").forEach((el) => {
        try {
          const s = getComputedStyle(el);
          if (s.fontVariantNumeric && s.fontVariantNumeric.includes("tabular")) n++;
        } catch {}
      });
      return n;
    })(),
    focusVisibleRules: [...document.styleSheets].reduce((acc, sheet) => {
      try {
        return (
          acc +
          [...sheet.cssRules].filter(
            (r) => r.selectorText && r.selectorText.includes("focus-visible")
          ).length
        );
      } catch {
        return acc;
      }
    }, 0),
  }));
  if (a11y.skipLink) ok("skip-to-content link present");
  else fail("skip-to-content link present");

  if (a11y.ariaHiddenCount >= 100) ok("decorative icons aria-hidden", a11y.ariaHiddenCount + "/" + a11y.svgCount);
  else if (a11y.ariaHiddenCount > 0) fail("decorative icons aria-hidden", `only ${a11y.ariaHiddenCount}/${a11y.svgCount} (expected 100+)`);
  else fail("decorative icons aria-hidden", "none found");

  if (a11y.tabularNumsCount >= 3) ok("tabular-nums applied", `${a11y.tabularNumsCount} elements`);
  else if (a11y.tabularNumsCount > 0) fail("tabular-nums applied", `only ${a11y.tabularNumsCount} (needs 3+, e.g. 0 on empty history view)`);
  else fail("tabular-nums applied", "none found — navigate to 生成记录 / 设置 to exercise numerics");

  if (a11y.focusVisibleRules >= 2) ok("focus-visible rules in stylesheets", `${a11y.focusVisibleRules} rules`);
  else fail("focus-visible rules in stylesheets", `${a11y.focusVisibleRules} (expected 2+)`);

  // ──────────────────────────────────────────────
  // 6. i18n: switch to English, verify title + lang change
  // ──────────────────────────────────────────────
  console.log("\n[6] i18n dynamic title + lang (requires login)");
  // This would need real credentials — skip gracefully if unauthenticated.
  if (page.url().includes("/auth")) {
    console.log("    \u2193  skipped (no login session, would need credentials)");
    console.log("      manual check: login → Settings → switch to English → title should become");
    console.log("      \"Xiangmushu\" and <html lang> should become \"en-US\"");
  } else {
    const langNow = await page.evaluate(() => document.documentElement.lang);
    if (langNow === "zh-CN") ok("default lang is zh-CN", langNow);
    else fail("default lang is zh-CN", langNow);
  }

  // ──────────────────────────────────────────────
  // 7. Sanity: every page reachable, no 502 / 404
  // ──────────────────────────────────────────────
  console.log("\n[7] Page reachability");
  const routes = ["/", "/auth", "/auth/login"];
  for (const r of routes) {
    const resp = await page.goto(BASE + r, { waitUntil: "domcontentloaded" });
    const status = resp?.status() ?? "n/a";
    if (typeof status === "number" && status < 400) ok(`${r} → ${status}`);
    else fail(`${r} → ${status}`);
  }

  await browser.close();

  // ──────────────────────────────────────────────
  console.log("\n════════════════════════════════════════");
  console.log(`  TOTAL  ${passed} passed / ${failed} failed`);
  console.log("════════════════════════════════════════");
  if (failures.length) {
    console.log("\nFailures:");
    failures.forEach((f, i) => console.log(`  ${i + 1}. ${f.name}  —  ${f.detail}`));
    process.exit(1);
  } else {
    console.log("\n\u2714  All design-system checks passed on production.\n");
  }
})().catch((err) => {
  console.error("Script crashed:", err);
  process.exit(2);
});
