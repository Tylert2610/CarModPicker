/**
 * The `redirect_uri` the identity handoff page sends the user back to.
 *
 * Row 6's page (frontend/src/pages/authentication/ExtensionHandoff.tsx) ends by
 * replacing the location with `<redirect_uri>#code=...&state=...`. It insists
 * that the redirect target is a `chrome-extension:` URL whose host is an id it
 * was built to trust, which is why this page exists rather than a
 * `chromiumapp.org` callback: a page inside the extension is the only redirect
 * target that contract accepts.
 *
 * A fragment is never sent to a server, so the code does not appear in any
 * access log between the web app and here. This page reads it, hands it to the
 * service worker, which is the only place a token is ever stored, and then
 * clears it from the address bar so it does not sit in browser history.
 */

const heading = document.getElementById("heading");
const detail = document.getElementById("detail");

function report(title: string, message: string): void {
  if (heading) heading.textContent = title;
  if (detail) detail.textContent = message;
}

async function run(): Promise<void> {
  // `location.hash` still carries the leading '#'.
  const fragment = new URLSearchParams(globalThis.location.hash.slice(1));
  const code = fragment.get("code") ?? "";
  const state = fragment.get("state") ?? "";

  // Drop the code from the address bar and from history before doing anything
  // else with it.
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
    // The worker closes this tab on success. If it could not, say so rather
    // than leaving a blank page.
    report("Signed in", "You can close this tab.");
    return;
  }

  report(
    "Sign in did not complete",
    response?.error ?? "The sign in could not be completed. Try again from the extension.",
  );
}

void run();
