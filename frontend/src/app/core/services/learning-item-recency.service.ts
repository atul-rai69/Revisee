import { Injectable } from '@angular/core';

interface ExplorationEntry {
  id: number;
  exploredAt: number;
}

const STORAGE_KEY = 'revisee.learning-item-exploration.v1';
const MAX_ENTRIES = 100;

@Injectable({ providedIn: 'root' })
export class LearningItemRecencyService {
  markExplored(itemId: number, exploredAt = Date.now()): void {
    if (!Number.isInteger(itemId) || itemId <= 0) return;
    const entries = this.read().filter((entry) => entry.id !== itemId);
    entries.unshift({ id: itemId, exploredAt });
    this.write(entries.slice(0, MAX_ENTRIES));
  }

  exploredAt(itemId: number): number | null {
    return this.read().find((entry) => entry.id === itemId)?.exploredAt ?? null;
  }

  remove(itemId: number): void {
    this.write(this.read().filter((entry) => entry.id !== itemId));
  }

  private read(): ExplorationEntry[] {
    try {
      const raw = globalThis.localStorage?.getItem(STORAGE_KEY);
      if (!raw) return [];
      const parsed: unknown = JSON.parse(raw);
      if (!Array.isArray(parsed)) return [];
      return parsed.filter((entry): entry is ExplorationEntry => {
        if (typeof entry !== 'object' || entry === null) return false;
        const value = entry as Partial<ExplorationEntry>;
        return Number.isInteger(value.id) && Number(value.id) > 0
          && typeof value.exploredAt === 'number' && Number.isFinite(value.exploredAt);
      });
    } catch {
      return [];
    }
  }

  private write(entries: ExplorationEntry[]): void {
    try {
      globalThis.localStorage?.setItem(STORAGE_KEY, JSON.stringify(entries));
    } catch {
      // Storage may be unavailable in privacy mode. The learning flow remains usable.
    }
  }
}
