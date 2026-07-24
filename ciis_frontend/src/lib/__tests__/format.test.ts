import { describe, expect, it } from "vitest";

import { formatBytes, formatPercent, titleCase, truncateHash } from "@/lib/format";

describe("format utilities", () => {
  it("formatBytes renders human sizes and guards junk", () => {
    expect(formatBytes(0)).toBe("—");
    expect(formatBytes(512)).toBe("512 B");
    expect(formatBytes(1024)).toBe("1.0 KB");
    expect(formatBytes(5 * 1024 * 1024)).toBe("5.0 MB");
    expect(formatBytes("not a number")).toBe("—");
  });

  it("formatPercent handles fractions and nullish", () => {
    expect(formatPercent(42)).toBe("42.0%");
    expect(formatPercent(0.42, true)).toBe("42.0%");
    expect(formatPercent(null)).toBe("—");
  });

  it("titleCase normalises separators", () => {
    expect(titleCase("high_priority")).toBe("High Priority");
    expect(titleCase("no-relationship")).toBe("No Relationship");
  });

  it("truncateHash shortens with an ellipsis", () => {
    expect(truncateHash("abcdef1234567890", 6)).toBe("abcdef…");
    expect(truncateHash(undefined)).toBe("—");
  });
});
