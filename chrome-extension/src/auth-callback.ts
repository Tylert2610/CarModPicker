/**
 * The `redirect_uri` the identity handoff page sends the user back to. It reads
 * the sign in code out of the URL fragment, hands it to the service worker,
 * and clears it from the address bar so it stays out of browser history.
 */

const heading = document.getElementById("heading");
const detail = document.getElementById("detail");

/** Show the outcome of the sign in on the page. */
function report(title: string, message: string): void {
  if (heading) heading.textContent = title;
  if (detail) detail.textContent = message;
}

/** Read the fragment and ask the service worker to finish the sign in. */
async function run(): Promise<void> {
  const fragment = new URLSearchParams(globalThis.location.hash.slice(1));
  const code = fragment.get("code") ?? "";
  const state = fragment.get("state") ?? "";

  globalThis.history.replaceState(null, "", globalThis.location.pathname);

  if (code === "") {
    report("Sign in did not complete", "No sign in code came back. Try again from the extension.");
    return;
  }

  let response: { success?: boolean; error?: string } | undefined;
  try {
    response = (await chrome.runtime.sendMessage({
      action: "completeIdentityAuth",
      code,
      state,
    })) as { success?: boolean; error?: string } | undefined;
  } catch (e) {
    report(
      "Sign in did not complete",
      e instanceof Error ? e.message : String(e),
    );
    return;
  }

  if (response?.success) {
    report("Signed in", "You can close this tab.");
    return;
  }

  report(
    "Sign in did not complete",
    response?.error ?? "The sign in could not be completed. Try again from the extension.",
  );
}

void run();
