import { useEffect, useState } from "react";
import LoginScreen from "../components/popup/LoginScreen";
import MainScreen from "../components/popup/MainScreen";
import PartDialog from "../components/popup/PartDialog";
import type { ScrapedProductData, User } from "../types";

/** Extension popup: signs the user in, then pulls in the current page. */
function Popup() {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [showPartDialog, setShowPartDialog] = useState(false);
  const [scrapedData, setScrapedData] = useState<ScrapedProductData | null>(
    null
  );
  const [statusMessage, setStatusMessage] = useState<{
    message: string;
    type: "info" | "success" | "error";
  } | null>(null);

  useEffect(() => {
    checkAuthStatus();
  }, []);

  useEffect(() => {
    const body = document.body;
    if (showPartDialog) {
      body.style.width = "800px";
    } else {
      body.style.width = "400px";
    }
  }, [showPartDialog]);

  /** Load the signed in user, leaving the user null when there is none. */
  const checkAuthStatus = async () => {
    try {
      const response = (await sendMessage({
        action: "getCurrentUser",
      })) as { success: boolean; data?: User };

      if (response.success && response.data) {
        setUser(response.data);
      } else {
        setUser(null);
      }
    } catch {
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  };

  const handleLogin = (userData: User) => {
    setUser(userData);
  };

  const handleLogout = async () => {
    await sendMessage({ action: "logout" });
    setUser(null);
  };

  /** Capture the active tab's HTML and open the part dialog on the result. */
  const handleScrape = async () => {
    try {
      const [tab] = await chrome.tabs.query({
        active: true,
        currentWindow: true,
      });
      if (!tab?.id || !tab.url) {
        showStatus("No active tab found", "error");
        return;
      }

      showStatus("Analyzing page...", "info");

      let pageHtml: string;
      try {
        const results = await chrome.scripting.executeScript({
          target: { tabId: tab.id },
          func: () => document.documentElement.outerHTML,
        });
        const firstResult = results?.[0]?.result;
        if (typeof firstResult !== "string" || !firstResult) {
          showStatus(
            "Failed to capture page HTML. Try refreshing the page.",
            "error"
          );
          return;
        }
        pageHtml = firstResult;
      } catch (injectError) {
        const msg =
          injectError instanceof Error
            ? injectError.message
            : String(injectError);
        if (msg.includes("Cannot access") || msg.includes("restricted")) {
          showStatus(
            "Can't pull from this page. Try a product page on a regular website.",
            "error"
          );
        } else {
          showStatus(
            `Failed to capture page: ${msg}. Try refreshing the page.`,
            "error"
          );
        }
        return;
      }

      chrome.runtime.sendMessage(
        { action: "scrapeAndParse", url: tab.url, html: pageHtml },
        (
          serverResponse:
            | {
                success: boolean;
                data?: ScrapedProductData & { adapter_used?: string };
                error?: string;
              }
            | undefined
        ) => {
          void chrome.runtime.lastError;
          if (!serverResponse?.success || !serverResponse.data) {
            showStatus(
              serverResponse?.error ||
                "Server failed to parse page. Check your connection and try again.",
              "error"
            );
            return;
          }
          setScrapedData(serverResponse.data);
          setShowPartDialog(true);
          setStatusMessage(null);
        }
      );
    } catch (error) {
      showStatus(
        "Error pulling from page: " +
          (error instanceof Error ? error.message : "Unknown error"),
        "error"
      );
    }
  };

  /** Show a status banner, clearing a success one after a few seconds. */
  const showStatus = (message: string, type: "info" | "success" | "error") => {
    setStatusMessage({ message, type });
    if (type === "success") {
      setTimeout(() => {
        setStatusMessage(null);
      }, 3000);
    }
  };

  const handlePartCreated = () => {
    setShowPartDialog(false);
    setScrapedData(null);
    showStatus("Part created successfully!", "success");
  };

  type SendMessageParams = {
    action: string;
    partData?: unknown;
    imageUrl?: string;
    limit?: number;
    searchTerm?: string;
  };

  /** Send one message to the service worker and resolve with its reply. */
  const sendMessage = (message: SendMessageParams): Promise<unknown> => {
    return new Promise((resolve, reject) => {
      chrome.runtime.sendMessage(message, (response: unknown) => {
        if (chrome.runtime.lastError) {
          reject(new Error(chrome.runtime.lastError.message));
        } else {
          resolve(response);
        }
      });
    });
  };

  if (isLoading) {
    return (
      <div className="w-full min-h-[200px] flex items-center justify-center">
        <div className="text-white/60">Loading...</div>
      </div>
    );
  }

  const containerClasses = showPartDialog
    ? "w-full min-h-[600px] max-h-[600px] overflow-y-auto"
    : "w-full overflow-y-auto";

  return (
    <div className={containerClasses}>
      <div className="w-full px-4 py-3 border-b border-white/10 bg-linear-to-r from-neutral-900/50 to-neutral-800/50 backdrop-blur-sm">
        <h1 className="text-sm font-semibold text-white/90 tracking-wide">
          CarModPicker
        </h1>
      </div>

      {!user ? (
        <LoginScreen onLogin={handleLogin} sendMessage={sendMessage} />
      ) : (
        <MainScreen
          user={user}
          onLogout={handleLogout}
          onScrape={handleScrape}
          statusMessage={statusMessage}
        />
      )}

      {showPartDialog && scrapedData && (
        <PartDialog
          scrapedData={scrapedData}
          onClose={() => {
            setShowPartDialog(false);
            setScrapedData(null);
          }}
          onPartCreated={handlePartCreated}
          sendMessage={sendMessage}
        />
      )}
    </div>
  );
}

export default Popup;
