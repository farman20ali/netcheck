/**
 * NetCheck Auto-Installer
 *
 * Checks whether `netcheckx` (≥ REQUIRED_VERSION) is installed under the
 * configured Python interpreter and offers to install / upgrade it via pip
 * if it is missing or outdated.
 *
 * Called once during extension activation before the MCP server starts.
 */

import { execFile } from "child_process";
import * as vscode from "vscode";

/** Minimum netcheckx version the extension requires. */
const REQUIRED_VERSION = "2.5.0";

/** Compare two semver strings. Returns true if `a` >= `b`. */
function semverGte(a: string, b: string): boolean {
  const parse = (v: string) => v.split(".").map((n) => parseInt(n, 10) || 0);
  const [aMaj, aMin, aPat] = parse(a);
  const [bMaj, bMin, bPat] = parse(b);
  if (aMaj !== bMaj) return aMaj > bMaj;
  if (aMin !== bMin) return aMin > bMin;
  return aPat >= bPat;
}

/** Run a command and return stdout, or throw on non-zero exit. */
function exec(cmd: string, args: string[]): Promise<string> {
  return new Promise((resolve, reject) => {
    execFile(cmd, args, { timeout: 15_000 }, (err, stdout, stderr) => {
      if (err) {
        reject(new Error(stderr || err.message));
      } else {
        resolve(stdout.trim());
      }
    });
  });
}

/**
 * Returns the installed netcheckx version string, or null if not found.
 */
async function getInstalledVersion(python: string): Promise<string | null> {
  try {
    // python -c "import netcheck; print(netcheck.__version__)"
    const out = await exec(python, [
      "-c",
      "import netcheck; print(netcheck.__version__)",
    ]);
    return out || null;
  } catch {
    return null;
  }
}

/**
 * Install or upgrade netcheckx using pip with a progress notification.
 */
async function pipInstall(python: string): Promise<void> {
  await vscode.window.withProgress(
    {
      location: vscode.ProgressLocation.Notification,
      title: "NetCheck: Installing netcheckx…",
      cancellable: false,
    },
    async (progress) => {
      progress.report({ message: `pip install netcheckx>=${REQUIRED_VERSION}` });
      await exec(python, [
        "-m",
        "pip",
        "install",
        "--quiet",
        "--upgrade",
        `netcheckx>=${REQUIRED_VERSION}`,
      ]);
    }
  );
}

/**
 * Main entry point — call this from activate() before starting the MCP server.
 *
 * Behaviour:
 *  - If netcheckx is installed and version is OK → silent no-op.
 *  - If missing or outdated → prompt user, then auto-install on approval.
 *  - On pip failure → show error with manual install instructions.
 */
export async function ensureNetcheckInstalled(
  context: vscode.ExtensionContext
): Promise<boolean> {
  const config = vscode.workspace.getConfiguration("netcheck");
  const python = config.get<string>("pythonPath", "python");

  const installed = await getInstalledVersion(python);

  if (installed && semverGte(installed, REQUIRED_VERSION)) {
    // All good — already at required version
    console.log(`[NetCheck] netcheckx ${installed} is installed and up-to-date.`);
    return true;
  }

  const message = installed
    ? `NetCheck requires netcheckx ≥ ${REQUIRED_VERSION} (found ${installed}). Upgrade now?`
    : `NetCheck requires netcheckx ≥ ${REQUIRED_VERSION}. Install it now via pip?`;

  const choice = await vscode.window.showInformationMessage(
    message,
    { modal: false },
    "Install / Upgrade",
    "Not Now"
  );

  if (choice !== "Install / Upgrade") {
    vscode.window.showWarningMessage(
      `NetCheck: netcheckx not installed. Run: pip install "netcheckx>=${REQUIRED_VERSION}"`
    );
    return false;
  }

  try {
    await pipInstall(python);
    const newVersion = await getInstalledVersion(python);
    vscode.window.showInformationMessage(
      `NetCheck: netcheckx ${newVersion ?? REQUIRED_VERSION} installed successfully! ✅`
    );
    return true;
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    const action = await vscode.window.showErrorMessage(
      `NetCheck: pip install failed — ${msg}`,
      "Show Manual Steps"
    );
    if (action === "Show Manual Steps") {
      vscode.env.openExternal(
        vscode.Uri.parse("https://github.com/farman20ali/netcheck#installation")
      );
    }
    return false;
  }
}
