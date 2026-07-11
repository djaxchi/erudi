// Model capability helpers shared by the chat composer.
//
// Whether the image-attach affordance should be enabled for a model. Permissive
// by design: attaching is disabled ONLY when the backend reports an explicit
// `supports_vision === false`, so a model whose capability is unknown (null,
// e.g. a fresh boot before detection) is never wrongly blocked (#133).
export function canAttachImages(model) {
  return model?.supports_vision !== false;
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
