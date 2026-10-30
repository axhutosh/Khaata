// One colour per category, everywhere (see docs/DESIGN.md). Keep in step with
// backend/app/extractor.py CATEGORIES.
export const CAT_COLORS = {
  "Food & Dining": "#E2663B",
  "Groceries": "#4F9D3A",
  "Shopping": "#3B6FE2",
  "Bills & Utilities": "#0E9488",
  "Health & Medical": "#C23B4E",
  "Transport": "#7C4DE2",
  "Fuel": "#8C5A3C",
  "Travel": "#2F8FB8",
  "Entertainment": "#D4477E",
  "Personal Care": "#C98A12",
  "Education": "#2D4E8F",
  "Rent & Housing": "#6E7A2E",
  "Insurance": "#B08A2E",
  "Cash": "#8A9099",
  "Bank Fees": "#6B7280",
  "Investments": "#2F6F5E",
  "Income": "#0E7C66",
  "Cashback": "#9A7BC4",
  "Transfer · Person": "#A3A7AE",
  "Uncategorised": "#B0B4BB",
};

const FALLBACK = ["#E2663B", "#3B6FE2", "#0E9488", "#4F9D3A", "#D4477E", "#7C4DE2"];
export const catColor = (c, i = 0) => CAT_COLORS[c] || FALLBACK[i % FALLBACK.length];

// The quick-pick row on Review: the categories local UPI payees most often turn out to be.
export const QUICK_PICKS = [
  "Food & Dining", "Groceries", "Shopping", "Health & Medical", "Transport", "Transfer · Person",
];

export function CategoryDot({ category, size = 8 }) {
  return (
    <span aria-hidden="true" style={{ display: "inline-block", width: size, height: size, borderRadius: 999,
      background: catColor(category), flex: "0 0 auto" }} />
  );
}
