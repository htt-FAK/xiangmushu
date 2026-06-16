import { useCallback, useEffect, useState } from "react";
import { fetchApiKeyStatus } from "./api";
import { hasValidatedModelProvider } from "./models";
import type { ApiKeyStatus } from "./types";

/**
 * Track whether the DashScope API key is valid. Polls on mount,
 * window focus, visibility change, and custom `xiangmushu:apikey-status-changed` event.
 */
export function useApiKeyStatus(selectedModels: Array<string | null | undefined> = []) {
  const [hasValidatedKey, setHasValidatedKey] = useState(false);
  const [status, setStatus] = useState<ApiKeyStatus | null>(null);

  const refresh = useCallback(() => {
    fetchApiKeyStatus()
      .then((nextStatus) => {
        setStatus(nextStatus);
        setHasValidatedKey(hasValidatedModelProvider(nextStatus, selectedModels));
      })
      .catch(() => {
        setStatus(null);
        setHasValidatedKey(false);
      });
  }, [selectedModels]);

  useEffect(() => {
    setHasValidatedKey(hasValidatedModelProvider(status, selectedModels));
  }, [selectedModels, status]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    const refreshWhenVisible = () => {
      if (document.visibilityState === "visible") refresh();
    };
    window.addEventListener("focus", refresh);
    window.addEventListener("xiangmushu:apikey-status-changed", refresh);
    document.addEventListener("visibilitychange", refreshWhenVisible);
    return () => {
      window.removeEventListener("focus", refresh);
      window.removeEventListener("xiangmushu:apikey-status-changed", refresh);
      document.removeEventListener("visibilitychange", refreshWhenVisible);
    };
  }, [refresh]);

  return { hasValidatedKey, status, refreshApiKeyStatus: refresh };
}
