/**
 * Collision-aware layout for order labels on a price chart.
 *
 * Groups orders whose Y-coordinates are within `minGapPx` of each other,
 * then applies a simple force-layout to prevent overlap between groups.
 */

export interface OrderForLayout {
  id: string;
  gridIndex: number;
  side: "buy" | "sell";
  price: number;
  priceSell: number;
  amount: number;
  status: string;
}

export interface LabelGroup {
  /** All orders collapsed into this label */
  orders: OrderForLayout[];
  /** Y coordinate (pixels) after force-layout */
  y: number;
  /** Average price of the group (for display / sorting) */
  avgPrice: number;
  /** Min price in group */
  minPrice: number;
  /** Max price in group */
  maxPrice: number;
  /** "buy" | "sell" | "mixed" */
  tone: "buy" | "sell" | "mixed";
  /** Display text, e.g. "B#0, B#1 · 65919–65970" */
  label: string;
}

/**
 * Core grouping: cluster orders whose Y-positions are within minGapPx.
 * Orders are sorted by price descending (highest price = lowest Y on chart).
 */
export function groupOrdersByProximity(
  orders: OrderForLayout[],
  priceToY: (price: number) => number,
  minGapPx: number,
): LabelGroup[] {
  if (orders.length === 0) return [];

  // Each order produces a label at its relevant price (buy→price, sell→priceSell)
  const items = orders
    .map((o) => ({
      order: o,
      labelPrice: o.side === "buy" ? o.price : o.priceSell,
    }))
    .sort((a, b) => b.labelPrice - a.labelPrice); // highest price first (lowest Y)

  const groups: { orders: OrderForLayout[]; prices: number[] }[] = [];
  let currentGroup: { orders: OrderForLayout[]; prices: number[] } = {
    orders: [items[0].order],
    prices: [items[0].labelPrice],
  };

  for (let i = 1; i < items.length; i++) {
    const prevY = priceToY(items[i - 1].labelPrice);
    const currY = priceToY(items[i].labelPrice);
    // Y increases downward; lower price → higher Y
    if (Math.abs(currY - prevY) <= minGapPx) {
      currentGroup.orders.push(items[i].order);
      currentGroup.prices.push(items[i].labelPrice);
    } else {
      groups.push(currentGroup);
      currentGroup = {
        orders: [items[i].order],
        prices: [items[i].labelPrice],
      };
    }
  }
  groups.push(currentGroup);

  return groups.map((g) => {
    const minPrice = Math.min(...g.prices);
    const maxPrice = Math.max(...g.prices);
    const avgPrice = g.prices.reduce((s, p) => s + p, 0) / g.prices.length;

    const sides = new Set(g.orders.map((o) => o.side));
    const tone: "buy" | "sell" | "mixed" =
      sides.size === 1 ? (sides.has("buy") ? "buy" : "sell") : "mixed";

    const label = buildGroupLabel(g.orders, minPrice, maxPrice);

    return {
      orders: g.orders,
      y: priceToY(avgPrice),
      avgPrice,
      minPrice,
      maxPrice,
      tone,
      label,
    };
  });
}

function buildGroupLabel(
  orders: OrderForLayout[],
  minPrice: number,
  maxPrice: number,
): string {
  const ids = orders
    .map((o) => `${o.side === "buy" ? "B" : "S"}#${o.gridIndex}`)
    .join(", ");

  if (orders.length === 1) {
    const o = orders[0];
    const price = o.side === "buy" ? o.price : o.priceSell;
    return `${o.side === "buy" ? "B" : "S"}#${o.gridIndex} ${formatP(price)}`;
  }

  const priceRange =
    minPrice === maxPrice
      ? formatP(minPrice)
      : `${formatP(minPrice)}–${formatP(maxPrice)}`;

  return `${ids} · ${priceRange}`;
}

function formatP(p: number): string {
  if (p >= 1000) return p.toFixed(1);
  if (p >= 1) return p.toFixed(2);
  return p.toFixed(4);
}

/**
 * Force-layout: push overlapping groups apart so no two are closer than minGapPx.
 * Mutates the `y` field in-place and returns the same array.
 */
export function applyForceLayout(
  groups: LabelGroup[],
  minGapPx: number,
): LabelGroup[] {
  if (groups.length <= 1) return groups;

  // Sort by Y ascending
  groups.sort((a, b) => a.y - b.y);

  // Push down pass
  for (let i = 1; i < groups.length; i++) {
    const gap = groups[i].y - groups[i - 1].y;
    if (gap < minGapPx) {
      groups[i].y = groups[i - 1].y + minGapPx;
    }
  }

  // Push up pass (keep within reasonable bounds)
  for (let i = groups.length - 2; i >= 0; i--) {
    const gap = groups[i + 1].y - groups[i].y;
    if (gap < minGapPx) {
      groups[i].y = groups[i + 1].y - minGapPx;
    }
  }

  return groups;
}

/**
 * Main entry point: group orders by proximity and resolve overlaps.
 */
export function resolveOrderLabelLayout(
  orders: OrderForLayout[],
  priceToY: (price: number) => number,
  minGapPx = 22,
): LabelGroup[] {
  const groups = groupOrdersByProximity(orders, priceToY, minGapPx);
  return applyForceLayout(groups, minGapPx);
}
