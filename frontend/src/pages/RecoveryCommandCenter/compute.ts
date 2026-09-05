/**
 * Pure derivation helpers for the Recovery Command Center screen. Status/label
 * mappings shared with other screens live in @/utils/statusMaps; this module
 * re-exports them and adds the screen-specific aggregates. Nothing here
 * invents data.
 */

export {
  attemptBadge,
  humanizeAction,
  riskBadge,
  riskLevel,
  shieldBadge,
  type RiskLevel,
} from '@/utils/statusMaps';

// -- aggregates --------------------------------------------------------------

export function recoveryRate(
  failed: number,
  recovered: number,
): number | null {
  if (!failed || recovered === null || recovered === undefined) {
    return null;
  }
  return (recovered / failed) * 100;
}

export function percentOf(count: number, total: number): number {
  if (!total) {
    return 0;
  }
  return (count / total) * 100;
}

export interface TopAction {
  action: string;
  count: number;
  share: number;
}

export function topAction(counts: Record<string, number>): TopAction | null {
  let best: string | null = null;
  let bestCount = 0;
  for (const [action, count] of Object.entries(counts)) {
    if (action !== '' && count > bestCount) {
      best = action;
      bestCount = count;
    }
  }
  if (best === null) {
    return null;
  }
  const total = Object.values(counts).reduce((sum, count) => sum + count, 0);
  return {
    action: best,
    count: bestCount,
    share: percentOf(bestCount, total),
  };
}