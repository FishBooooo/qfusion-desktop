import { type ChildProcess, spawn } from "node:child_process";
import { once } from "node:events";
import { createRequire } from "node:module";
import { createServer } from "node:net";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { expect, test } from "@playwright/test";

interface ManagedProcess {
  readonly child: ChildProcess;
  readonly cwd: string;
  readonly name: string;
  readonly output: () => string;
  readonly pid: number;
  readonly port: number;
  readonly startupError: () => Error | undefined;
  readonly startedAt: string;
}

const REPOSITORY_ROOT = fileURLToPath(new URL("../../../", import.meta.url));
const DESKTOP_DIRECTORY = resolve(REPOSITORY_ROOT, "apps", "desktop");
const moduleRequire = createRequire(import.meta.url);
const VITE_ENTRYPOINT = resolve(
  dirname(moduleRequire.resolve("vite/package.json")),
  "bin",
  "vite.js",
);
const BACKEND_EXECUTABLE =
  process.platform === "win32"
    ? resolve(REPOSITORY_ROOT, ".venv", "Scripts", "qfusion-backend.exe")
    : resolve(REPOSITORY_ROOT, ".venv", "bin", "qfusion-backend");

let backendProcess: ManagedProcess | undefined;
let frontendProcess: ManagedProcess | undefined;
let frontendUrl = "";

function delay(milliseconds: number): Promise<void> {
  return new Promise((resolvePromise) => {
    setTimeout(resolvePromise, milliseconds);
  });
}

async function allocateDynamicPort(): Promise<number> {
  const server = createServer();

  await new Promise<void>((resolvePromise, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", resolvePromise);
  });

  const address = server.address();
  if (address === null || typeof address === "string") {
    server.close();
    throw new Error("The operating system did not allocate an IPv4 loopback port.");
  }

  const port = address.port;
  await new Promise<void>((resolvePromise, reject) => {
    server.close((error) => {
      if (error) {
        reject(error);
      } else {
        resolvePromise();
      }
    });
  });
  return port;
}

function startManagedProcess(
  name: string,
  command: string,
  args: string[],
  cwd: string,
  port: number,
  extraEnvironment: Record<string, string>,
): ManagedProcess {
  let bufferedOutput = "";
  let capturedStartupError: Error | undefined;
  const child = spawn(command, args, {
    cwd,
    env: { ...process.env, ...extraEnvironment },
    stdio: ["ignore", "pipe", "pipe"],
  });

  child.on("error", (error) => {
    capturedStartupError = error;
  });

  const appendOutput = (chunk: Buffer): void => {
    bufferedOutput = (bufferedOutput + chunk.toString("utf-8")).slice(-8_000);
  };
  child.stdout?.on("data", appendOutput);
  child.stderr?.on("data", appendOutput);

  if (child.pid === undefined) {
    throw new Error(`Failed to obtain the ${name} child-process handle.`);
  }

  const managedProcess: ManagedProcess = {
    child,
    cwd,
    name,
    output: () => bufferedOutput,
    pid: child.pid,
    port,
    startupError: () => capturedStartupError,
    startedAt: new Date().toISOString(),
  };
  process.stdout.write(
    `QFusion E2E started ${name}: pid=${managedProcess.pid} port=${port} cwd=${cwd} started_at=${managedProcess.startedAt}\n`,
  );
  return managedProcess;
}

async function waitForService(service: ManagedProcess, url: string): Promise<void> {
  const deadline = Date.now() + 30_000;

  while (Date.now() < deadline) {
    const startupError = service.startupError();
    if (startupError) {
      throw new Error(
        `${service.name} failed to start: ${startupError.message}\n${service.output()}`,
      );
    }
    if (service.child.exitCode !== null || service.child.signalCode !== null) {
      throw new Error(
        `${service.name} exited before readiness: exit=${service.child.exitCode} signal=${service.child.signalCode}\n${service.output()}`,
      );
    }

    try {
      const response = await fetch(url, {
        redirect: "error",
        signal: AbortSignal.timeout(2_000),
      });
      if (response.ok) {
        return;
      }
    } catch {
      // The owned child is still starting; retry only this recorded loopback endpoint.
    }
    await delay(200);
  }

  throw new Error(
    `Timed out waiting for ${service.name} on owned port ${service.port}.\n${service.output()}`,
  );
}

async function stopManagedProcess(service: ManagedProcess | undefined): Promise<void> {
  if (
    service === undefined ||
    service.child.exitCode !== null ||
    service.child.signalCode !== null
  ) {
    return;
  }
  if (service.child.pid !== service.pid) {
    throw new Error(`Refusing to stop ${service.name}: child-process identity changed.`);
  }

  const gracefulExit = once(service.child, "exit");
  service.child.kill("SIGTERM");
  await Promise.race([gracefulExit, delay(5_000)]);

  if (service.child.exitCode === null && service.child.signalCode === null) {
    const forcedExit = once(service.child, "exit");
    if (service.child.kill("SIGKILL")) {
      await forcedExit;
    }
  }

  process.stdout.write(
    `QFusion E2E stopped ${service.name}: pid=${service.pid} port=${service.port}\n`,
  );
}

test.beforeAll(async () => {
  const backendPort = await allocateDynamicPort();
  let frontendPort = await allocateDynamicPort();
  while (frontendPort === backendPort) {
    frontendPort = await allocateDynamicPort();
  }

  const backendUrl = `http://127.0.0.1:${backendPort}`;
  frontendUrl = `http://127.0.0.1:${frontendPort}`;

  backendProcess = startManagedProcess(
    "backend",
    BACKEND_EXECUTABLE,
    [],
    REPOSITORY_ROOT,
    backendPort,
    {
      QFUSION_ALLOWED_ORIGINS: JSON.stringify([frontendUrl]),
      QFUSION_ENVIRONMENT: "test",
      QFUSION_LLM_MODE: "off",
      QFUSION_PORT: String(backendPort),
    },
  );

  try {
    await waitForService(backendProcess, `${backendUrl}/api/v1/health`);
    frontendProcess = startManagedProcess(
      "frontend",
      process.execPath,
      [
        VITE_ENTRYPOINT,
        "--host",
        "127.0.0.1",
        "--port",
        String(frontendPort),
        "--strictPort",
      ],
      DESKTOP_DIRECTORY,
      frontendPort,
      {
        VITE_API_BASE_URL: backendUrl,
      },
    );
    await waitForService(frontendProcess, frontendUrl);
  } catch (error) {
    await Promise.allSettled([
      stopManagedProcess(frontendProcess),
      stopManagedProcess(backendProcess),
    ]);
    throw error;
  }
});

test.afterAll(async () => {
  await stopManagedProcess(frontendProcess);
  await stopManagedProcess(backendProcess);
});

test("renders synthetic analysis and connects to the M0 backend", async ({ page }) => {
  await page.goto(frontendUrl);

  await expect(page.getByRole("heading", { name: "合成科技样本" })).toBeVisible();
  await expect(page.getByText("SYNTHETIC_MOCK").first()).toBeVisible();
  await expect(page.getByText("PAPER_TRADE_ONLY")).toBeVisible();
  await expect(page.getByText(/仅用于界面与契约验证/)).toBeVisible();
  await expect(page.getByText("后端在线 · v0.1.0")).toBeVisible();
});
