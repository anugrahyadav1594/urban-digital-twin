export const inr = (crore: number) => "₹" + crore.toFixed(0) + " Cr";
export const pct = (n: number) => (n > 0 ? "+" : "") + n.toFixed(0) + "%";
export const num = (n: number) => n.toLocaleString("en-IN");
export const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));
export const uid = (p = "id") => p + "_" + Math.random().toString(36).slice(2, 9);
