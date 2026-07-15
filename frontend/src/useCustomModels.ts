import { useCallback } from "react";
import type { CustomModel } from "./types";

const CACHE_KEY_PREFIX = "custom_models_cache:";
const CACHE_TTL_MS = 5 * 60 * 1000;

interface CachedEntry<T> {
  data: T;
  timestamp: number;
}

export function useCustomModelsCache(userId: number | string | null) {
  const cacheKey = userId ? `${CACHE_KEY_PREFIX}${userId}` : null;

  const getModels = useCallback((): CustomModel[] | null => {
    if (!cacheKey) return null;
    const raw = localStorage.getItem(cacheKey);
    if (!raw) return null;

    try {
      const entry: CachedEntry<CustomModel[]> = JSON.parse(raw);
      const isExpired = Date.now() - entry.timestamp > CACHE_TTL_MS;
      if (isExpired) {
        localStorage.removeItem(cacheKey);
        return null;
      }
      return entry.data;
    } catch (e) {
      localStorage.removeItem(cacheKey);
      return null;
    }
  }, [cacheKey]);

  const setModels = useCallback(
    (models: CustomModel[]) => {
      if (!cacheKey) return;
      const entry: CachedEntry<CustomModel[]> = {
        data: models,
        timestamp: Date.now(),
      };
      localStorage.setItem(cacheKey, JSON.stringify(entry));
    },
    [cacheKey]
  );

  const invalidate = useCallback(() => {
    if (cacheKey) {
      localStorage.removeItem(cacheKey);
    }
  }, [cacheKey]);

  return { getModels, setModels, invalidate };
}
