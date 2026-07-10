import { describe, it, expect } from "vitest";
import { transformAppStartupInfo } from "./hardwareTransform";

// transformAppStartupInfo feeds the app-startup hardware readout and the
// "Models For You" size window (#86). Two behaviours matter and must not drift:
// a null/undefined payload returns a safe zeroed "unknown" shape (never throws,
// never yields undefined scores the UI would render as NaN), and a real payload
// is mapped field-for-field with the recommended param window preserved.

describe("transformAppStartupInfo", () => {
  it("returns a safe zeroed 'unknown' shape when data is missing", () => {
    for (const empty of [null, undefined]) {
      expect(transformAppStartupInfo(empty)).toEqual({
        backend_type: "unknown",
        global_inference_score: 0,
        global_inference_label: "Unknown",
        raw_inference_score: 0,
        recommended_param_min: null,
        recommended_param_max: null,
      });
    }
  });

  it("maps a full payload field-for-field", () => {
    const out = transformAppStartupInfo({
      backend_type: "cuda",
      global_inference_score: 82,
      global_inference_label: "Fast",
      raw_inference_score: 71,
      recommended_param_min: 4,
      recommended_param_max: 8,
    });

    expect(out).toEqual({
      backend_type: "cuda",
      global_inference_score: 82,
      global_inference_label: "Fast",
      raw_inference_score: 71,
      recommended_param_min: 4,
      recommended_param_max: 8,
    });
  });

  it("preserves the recommended param window as given, including nulls", () => {
    // The backend can report an open-ended window; the transform must pass the
    // exact min/max (including null) through, not coerce or default them.
    const out = transformAppStartupInfo({
      backend_type: "cpu",
      global_inference_score: 10,
      global_inference_label: "Slow",
      raw_inference_score: 10,
      recommended_param_min: null,
      recommended_param_max: 3,
    });

    expect(out.recommended_param_min).toBeNull();
    expect(out.recommended_param_max).toBe(3);
  });

  it("does not invent fields beyond the UI contract", () => {
    // A regression that spreads the raw payload would leak backend-only keys
    // into the UI object; the transform must return exactly the six fields.
    const out = transformAppStartupInfo({
      backend_type: "mlx",
      global_inference_score: 50,
      global_inference_label: "OK",
      raw_inference_score: 45,
      recommended_param_min: 2,
      recommended_param_max: 6,
      secret_backend_only_field: "leak",
    });

    expect(Object.keys(out).sort()).toEqual(
      [
        "backend_type",
        "global_inference_label",
        "global_inference_score",
        "raw_inference_score",
        "recommended_param_max",
        "recommended_param_min",
      ].sort()
    );
    expect(out).not.toHaveProperty("secret_backend_only_field");
  });
});
