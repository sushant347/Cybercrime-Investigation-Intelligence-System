import { AxiosError, AxiosHeaders } from "axios";
import { describe, expect, it } from "vitest";

import { apiErrorMessage } from "@/lib/apiClient";

function axiosErrorWith(status: number, data?: unknown, code?: string): AxiosError {
  const err = new AxiosError("boom", code);
  err.response = {
    status,
    data,
    statusText: "",
    headers: {},
    config: { headers: new AxiosHeaders() },
  } as never;
  return err;
}

describe("apiErrorMessage", () => {
  it("prefers the API's detail envelope", () => {
    const err = axiosErrorWith(400, { detail: "Unsupported file type '.exe'." });
    expect(apiErrorMessage(err)).toBe("Unsupported file type '.exe'.");
  });

  it("maps 403 to a permission message", () => {
    const err = axiosErrorWith(403, {});
    expect(apiErrorMessage(err)).toBe("You do not have permission to do this.");
  });

  it("maps a network error to a reachability message", () => {
    const err = new AxiosError("Network Error", "ERR_NETWORK");
    expect(apiErrorMessage(err)).toBe("Cannot reach the CIIS API server.");
  });

  it("falls back for unknown/non-axios errors", () => {
    expect(apiErrorMessage(new Error("weird"))).toBe(
      "Something went wrong. Please try again.",
    );
    expect(apiErrorMessage("a string")).toBe(
      "Something went wrong. Please try again.",
    );
  });
});
