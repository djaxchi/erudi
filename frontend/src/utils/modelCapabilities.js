// Model capability helpers shared by the chat composer.
//
// Whether the image-attach affordance should be enabled for a model. Permissive
// by design: attaching is disabled ONLY when the backend reports an explicit
// `supports_vision === false`, so a model whose capability is unknown (null,
// e.g. a fresh boot before detection) is never wrongly blocked (#133).
export function canAttachImages(model) {
  return model?.supports_vision !== false;
}

// How many images the composer allows per turn for a given model. More capable
// models have more context to spend on image tokens, so scale the cap with the
// model's parameter size. This is a proxy: the backend does not expose a
// context-window field, and param_size is the closest available signal. Unknown
// size falls back to a sensible default. Callers only reach this for
// vision-capable models (the attach affordance is hidden otherwise).
export function maxImagesForModel(model) {
  const size = model?.param_size;
  if (typeof size !== "number" || size <= 0) return 4; // unknown -> default
  if (size < 3) return 2;
  if (size < 8) return 4;
  return 6;
}

// Whether a model can read image input, for the capability badge on model cards.
// Unlike `canAttachImages` (permissive: everything except an explicit false),
// this is a POSITIVE signal — true only when we can affirm vision support — so a
// card shows the image icon only for models we know are multimodal.
//   - `supports_vision === true`: an installed model the engine detected as a VLM.
//   - `category === "vision"`: the pre-download signal — the catalog/HF-search
//     buckets multimodal models into "Vision & Multimodal" from their pipeline
//     tag / name, so it's available before a model is downloaded (when
//     `supports_vision` is still null).
export function modelSupportsVision(model) {
  if (!model) return false;
  if (model.supports_vision === true) return true;
  return model.category === "vision";
}
