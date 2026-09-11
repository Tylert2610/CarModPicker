import { useEffect, useState } from "react";

const API_URLS = {
  production: "https://api.carmodpicker.com/api",
  staging: "https://api.staging.carmodpicker.com/api",
  localhost: "http://localhost:8000/api",
} as const;

type ApiEnvironment = keyof typeof API_URLS;

/**
 * Which sign in the extension uses.
 *
 * The web app switches on `VITE_AUTH_MODE`, a build time flag. The extension
 * ships one artifact to the store and has no build time env plumbing, so the
 * equivalent here is this runtime setting. It stays on `legacy` until row 12
 * of docs/identity-adoption.md cuts over, so an existing install is unchanged
 * until someone deliberately flips it.
 */
type AuthMode = "legacy" | "identity";

const DEFAULT_AUTH_MODE: AuthMode = "legacy";

function Options() {
  const [environment, setEnvironment] = useState<ApiEnvironment>("production");
  const [openPartAfterCreation, setOpenPartAfterCreation] = useState(true);
  const [openInNewTab, setOpenInNewTab] = useState(true);
  const [apiKey, setApiKey] = useState("");
  const [authMode, setAuthMode] = useState<AuthMode>(DEFAULT_AUTH_MODE);
  const [status, setStatus] = useState<{
    message: string;
    type: "success" | "error";
  } | null>(null);

  useEffect(() => {
    // Load saved settings
    chrome.storage.sync.get(
      ["apiUrl", "openPartAfterCreation", "openInNewTab", "authMode"],
      (result) => {
        const apiUrl = result["apiUrl"];
        if (apiUrl && typeof apiUrl === "string") {
          const env = getEnvironmentFromUrl(apiUrl);
          setEnvironment(env);
        }
        if (result["openPartAfterCreation"] !== undefined) {
          setOpenPartAfterCreation(result["openPartAfterCreation"] as boolean);
        }
        if (result["openInNewTab"] !== undefined) {
          setOpenInNewTab(result["openInNewTab"] as boolean);
        }
        // Anything other than the exact string falls back to legacy, so a
        // stale or malformed value cannot switch the flow on by accident.
        setAuthMode(result["authMode"] === "identity" ? "identity" : "legacy");
      },
    );

    // The API key lives in `local`, not `sync`: it is a shared secret and
    // `sync` would replicate it to every Chrome profile the user signs into.
    chrome.storage.local.get(["apiKey"], (result) => {
      const stored = result["apiKey"];
      if (typeof stored === "string") {
        setApiKey(stored);
      }
    });
  }, []);

  const getEnvironmentFromUrl = (apiUrl: string): ApiEnvironment => {
    if (apiUrl.includes("localhost") || apiUrl.includes("127.0.0.1")) {
      return "localhost";
    }
    if (apiUrl.includes("staging")) {
      return "staging";
    }
    return "production";
  };

  const handleSave = async () => {
    if (!environment || !API_URLS[environment]) {
      setStatus({ message: "Invalid environment selected", type: "error" });
      return;
    }

    const apiUrl = API_URLS[environment];
    await chrome.storage.sync.set({
      apiUrl,
      openPartAfterCreation,
      openInNewTab,
      authMode,
    });

    const trimmedApiKey = apiKey.trim();
    if (trimmedApiKey) {
      await chrome.storage.local.set({ apiKey: trimmedApiKey });
    } else {
      await chrome.storage.local.remove(["apiKey"]);
    }
    setApiKey(trimmedApiKey);
    setStatus({ message: "Settings saved successfully!", type: "success" });

    setTimeout(() => {
      setStatus(null);
    }, 3000);
  };

  return (
    <div className="min-h-screen p-10">
      <div className="max-w-2xl mx-auto">
        <h1 className="text-3xl font-bold text-gradient mb-8">
          CarModPicker Extension Settings
        </h1>

        <div className="glass-card rounded-2xl p-6 space-y-6">
          <div>
            <h2 className="text-xl font-semibold text-white mb-4 pb-2 border-b border-white/10">
              General Settings
            </h2>
            <div className="space-y-4">
              <div>
                <label className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={openPartAfterCreation}
                    onChange={(e) => setOpenPartAfterCreation(e.target.checked)}
                    className="w-5 h-5 rounded border-white/20 bg-white/10 text-primary-500 focus:ring-2 focus:ring-primary-500/50 focus:ring-offset-2 focus:ring-offset-neutral-900 cursor-pointer"
                  />
                  <div>
                    <div className="text-sm font-medium text-neutral-300">
                      Open part page after creation
                    </div>
                    <div className="text-xs text-neutral-400">
                      Automatically navigate to the created part's page on the
                      frontend
                    </div>
                  </div>
                </label>
              </div>

              {openPartAfterCreation && (
                <div className="ml-8">
                  <label className="flex items-center gap-3 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={openInNewTab}
                      onChange={(e) => setOpenInNewTab(e.target.checked)}
                      className="w-5 h-5 rounded border-white/20 bg-white/10 text-primary-500 focus:ring-2 focus:ring-primary-500/50 focus:ring-offset-2 focus:ring-offset-neutral-900 cursor-pointer"
                    />
                    <div>
                      <div className="text-sm font-medium text-neutral-300">
                        Open in new tab
                      </div>
                      <div className="text-xs text-neutral-400">
                        If unchecked, opens in the current tab
                      </div>
                    </div>
                  </label>
                </div>
              )}

              <div className="pt-2 border-t border-white/10">
                <label className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={authMode === "identity"}
                    onChange={(e) =>
                      setAuthMode(e.target.checked ? "identity" : "legacy")
                    }
                    className="w-5 h-5 rounded border-white/20 bg-white/10 text-primary-500 focus:ring-2 focus:ring-primary-500/50 focus:ring-offset-2 focus:ring-offset-neutral-900 cursor-pointer"
                  />
                  <div>
                    <div className="text-sm font-medium text-neutral-300">
                      Use the new sign in
                    </div>
                    <div className="text-xs text-neutral-400">
                      Signs in through the CarModPicker website and hands the
                      result straight back to the extension. Leave this off
                      unless you have been asked to try it.
                    </div>
                  </div>
                </label>
              </div>
            </div>
          </div>

          <div>
            <h2 className="text-xl font-semibold text-white mb-4 pb-2 border-b border-white/10">
              Developer Settings
            </h2>
            <label
              htmlFor="apiEnvironment"
              className="block text-sm font-medium text-neutral-300 mb-2"
            >
              API Environment
            </label>
            <select
              id="apiEnvironment"
              value={environment}
              onChange={(e) => setEnvironment(e.target.value as ApiEnvironment)}
              className="w-full px-5 py-4 rounded-2xl bg-linear-to-br from-white/10 to-white/5 border border-white/20 text-white text-sm transition-all duration-300 backdrop-blur-[15px] focus:outline-none focus:border-primary-500 focus:ring-4 focus:ring-primary-500/15 focus:bg-linear-to-br focus:from-white/15 focus:to-white/8 focus:-translate-y-px disabled:opacity-50 disabled:cursor-not-allowed appearance-none cursor-pointer"
              style={{
                backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%3E%3Cpath fill='white' d='M6 9L1 4h10z'/%3E%3C/svg%3E")`,
                backgroundRepeat: "no-repeat",
                backgroundPosition: "right 1rem center",
                paddingRight: "2.5rem",
              }}
            >
              <option value="production" className="bg-neutral-900 text-white">
                Production
              </option>
              <option value="staging" className="bg-neutral-900 text-white">
                Staging
              </option>
              <option value="localhost" className="bg-neutral-900 text-white">
                Localhost
              </option>
            </select>
            <div className="mt-2 text-xs text-neutral-400">
              Select which API environment to use. Default: Production
            </div>

            <label
              htmlFor="apiKey"
              className="block text-sm font-medium text-neutral-300 mt-6 mb-2"
            >
              Ingestion API Key
            </label>
            <input
              id="apiKey"
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              autoComplete="off"
              spellCheck={false}
              placeholder="Leave blank unless you have been given one"
              className="w-full px-5 py-4 rounded-2xl bg-linear-to-br from-white/10 to-white/5 border border-white/20 text-white text-sm transition-all duration-300 backdrop-blur-[15px] placeholder:text-neutral-500 focus:outline-none focus:border-primary-500 focus:ring-4 focus:ring-primary-500/15 focus:bg-linear-to-br focus:from-white/15 focus:to-white/8 focus:-translate-y-px"
            />
            <div className="mt-2 text-xs text-neutral-400">
              Sent as the <code>X-API-Key</code> header on every API call. Only
              the batch price-history route requires it, and only ingestion
              builds of the extension are given a key. Stored on this device
              only, never synced across your Chrome profiles.
            </div>
          </div>

          <button
            onClick={handleSave}
            className="px-6 py-3 rounded-xl font-semibold bg-linear-to-r from-[#667eea] to-[#764ba2] bg-size-[200%_200%] text-white border-none transition-all duration-300 hover:translate-y-[-3px] hover:shadow-[0_15px_35px_rgba(102,126,234,0.4)] hover:animate-[gradientShift_3s_ease_infinite] relative overflow-hidden cursor-pointer"
          >
            Save Settings
          </button>

          {status && (
            <div
              className={`p-3 rounded-xl text-sm ${
                status.type === "success"
                  ? "bg-green-500/20 border border-green-500/50 text-green-200"
                  : "bg-red-500/20 border border-red-500/50 text-red-200"
              }`}
            >
              {status.message}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default Options;
