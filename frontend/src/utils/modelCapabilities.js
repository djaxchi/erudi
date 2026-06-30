// Model capability helpers shared by the chat composer.
//
// Whether the image-attach affordance should be enabled for a model. Permissive
// by design: attaching is disabled ONLY when the backend reports an explicit
// `supports_vision === false`, so a model whose capability is unknown (null,
// e.g. a fresh boot before detection) is never wrongly blocked (#133).
export function canAttachImages(model) {
  return model?.supports_vision !== false;
}
