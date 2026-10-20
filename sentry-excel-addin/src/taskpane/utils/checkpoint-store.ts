/**
 * IndexedDB-backed checkpoint persistence for workbook undo/restore.
 *
 * All operations are non-fatal — callers should catch errors so the add-in
 * continues to work even if IndexedDB is unavailable or quota is exceeded.
 */

import { openDB, type IDBPDatabase, type DBSchema } from "idb";
import type { SheetSnapshot, SerializedNamedRange } from "../../shared/types";

// ─── Schema ───

export interface StoredCheckpoint {
  messageId: string;
  threadId: string;
  timestamp: number;
  sheetNames: string[];
  sheets: Record<string, SheetSnapshot>;
  namedRanges: SerializedNamedRange[];
  sizeEstimate: number;
}

interface CheckpointDBSchema extends DBSchema {
  checkpoints: {
    key: string;
    value: StoredCheckpoint;
    indexes: {
      threadId: string;
      timestamp: number;
    };
  };
}

// ─── Constants ───

const DB_NAME = "sentry-checkpoints";
const DB_VERSION = 1;
const STORE_NAME = "checkpoints";
const STALE_DAYS = 7;

// ─── Singleton DB connection ───

let dbPromise: Promise<IDBPDatabase<CheckpointDBSchema>> | null = null;

function getDb(): Promise<IDBPDatabase<CheckpointDBSchema>> {
  if (!dbPromise) {
    dbPromise = openDB<CheckpointDBSchema>(DB_NAME, DB_VERSION, {
      upgrade(db) {
        const store = db.createObjectStore(STORE_NAME, { keyPath: "messageId" });
        store.createIndex("threadId", "threadId", { unique: false });
        store.createIndex("timestamp", "timestamp", { unique: false });
      },
      blocked() {
        console.warn("[checkpoint-store] DB blocked by older version");
      },
      blocking() {
        console.warn("[checkpoint-store] DB blocking newer version");
      },
    });

    // One-time stale cleanup on first open
    dbPromise.then(() => cleanupStaleCheckpoints(STALE_DAYS)).catch(() => {});
  }
  return dbPromise;
}

// ─── CRUD ───

export async function saveCheckpoint(cp: StoredCheckpoint): Promise<void> {
  try {
    const db = await getDb();
    await db.put(STORE_NAME, cp);
  } catch (err: unknown) {
    if (err instanceof DOMException && err.name === "QuotaExceededError") {
      console.warn("[checkpoint-store] Quota exceeded, running eviction...");
      await evictOldest(5);
      const db = await getDb();
      await db.put(STORE_NAME, cp);
    } else {
      throw err;
    }
  }
}

export async function loadCheckpoint(messageId: string): Promise<StoredCheckpoint | undefined> {
  const db = await getDb();
  return db.get(STORE_NAME, messageId);
}

export async function loadCheckpointsByThread(threadId: string): Promise<StoredCheckpoint[]> {
  const db = await getDb();
  const results = await db.getAllFromIndex(STORE_NAME, "threadId", threadId);
  return results.sort((a, b) => a.timestamp - b.timestamp);
}

export async function deleteCheckpoint(messageId: string): Promise<void> {
  const db = await getDb();
  await db.delete(STORE_NAME, messageId);
}

export async function deleteCheckpointsByThread(threadId: string): Promise<void> {
  const db = await getDb();
  const tx = db.transaction(STORE_NAME, "readwrite");
  const index = tx.store.index("threadId");
  let cursor = await index.openCursor(threadId);
  while (cursor) {
    await cursor.delete();
    cursor = await cursor.continue();
  }
  await tx.done;
}

// ─── Eviction ───

export async function enforceCheckpointLimits(threadId: string, maxPerThread: number): Promise<void> {
  const db = await getDb();
  const all = await db.getAllFromIndex(STORE_NAME, "threadId", threadId);
  if (all.length <= maxPerThread) return;

  all.sort((a, b) => a.timestamp - b.timestamp);
  const toDelete = all.slice(0, all.length - maxPerThread);
  const tx = db.transaction(STORE_NAME, "readwrite");
  for (const cp of toDelete) {
    tx.store.delete(cp.messageId);
  }
  await tx.done;
}

async function evictOldest(count: number): Promise<void> {
  const db = await getDb();
  const tx = db.transaction(STORE_NAME, "readwrite");
  const index = tx.store.index("timestamp");
  let cursor = await index.openCursor();
  let deleted = 0;
  while (cursor && deleted < count) {
    await cursor.delete();
    deleted++;
    cursor = await cursor.continue();
  }
  await tx.done;
}

export async function cleanupStaleCheckpoints(maxAgeDays: number): Promise<void> {
  const cutoff = Date.now() - maxAgeDays * 86_400_000;
  const db = await getDb();
  const tx = db.transaction(STORE_NAME, "readwrite");
  const index = tx.store.index("timestamp");
  const range = IDBKeyRange.upperBound(cutoff);
  let cursor = await index.openCursor(range);
  while (cursor) {
    await cursor.delete();
    cursor = await cursor.continue();
  }
  await tx.done;
}
