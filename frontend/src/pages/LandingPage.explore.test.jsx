// @vitest-environment jsdom
import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent, waitFor } from "@testing-library/react";

// Explore-panel behavior of LandingPage beyond the delete/download suites:
// the remote catalog feeds the recommended rail (certified picks deduped
// against flagships) and the collapsed community section; the welcome modal
// is gated by the hardware evaluation; startup fetch failures degrade
// gracefully; refresh/rebind/delete failures surface in the message modals;
// and the card actions navigate.

const { tracedFetchMock, navigateMock, ctx, sectionReloadSpy } = vi.hoisted(() => ({
  tracedFetchMock: vi.fn(),
  navigateMock: vi.fn(),
  ctx: { open: vi.fn(), completionCount: 0 },
  sectionReloadSpy: vi.fn(),
}));

vi.mock("../contexts/DownloadModalContext", () => ({
  useDownloadModal: () => ctx,
}));

vi.mock("../services/api/client", () => ({
  default: { get: vi.fn(async () => ({})) },
  apiClient: { get: vi.fn(async () => ({})) },
  tracedFetch: tracedFetchMock,
}));

vi.mock("react-router-dom", () => ({ useNavigate: () => navigateMock }));

vi.mock("../components/Sidebar", () => ({ default: () => null }));
vi.mock("../components/ConnectionStatus", () => ({ default: () => null }));
vi.mock("../components/MachineReadout", () => ({ default: () => null }));
vi.mock("../components/HuggingFaceSearchPanel", () => ({ default: () => null }));
vi.mock("../components/CategorySections", () => ({ default: () => null }));
vi.mock("../components/CatalogFilters", () => ({ default: () => null }));
vi.mock("../assets/images/logos/logoerudifinal.png", () => ({ default: "logo.png" }));

// The sidebar section exposes the imperative reload handle the page drives
// after downloads/deletes, plus the onLocalModelRefresh callback.
vi.mock("../components/ModelCollapsibleSection", async () => {
  const { forwardRef, useImperativeHandle } = await import("react");
  const Section = forwardRef(({ onLocalModelRefresh }, ref) => {
    useImperativeHandle(ref, () => ({ reloadLocalModels: sectionReloadSpy }));
    return <button onClick={() => onLocalModelRefresh()}>section-refresh</button>;
  });
  Section.displayName = "ModelCollapsibleSectionMock";
  return { default: Section };
});

vi.mock("../components/ExploreIndex", () => ({
  default: ({ onJump }) => <button onClick={() => onJump("explore-search")}>jump-search</button>,
}));

vi.mock("../components/ExploreModelCard", () => ({
  default: ({ model, onDownload, onInfo }) => (
    <div>
      <span>{`explore:${model.name}`}</span>
      <button onClick={() => onDownload(model)}>{`dl:${model.name}`}</button>
      <button onClick={() => onInfo(model)}>{`info:${model.name}`}</button>
    </div>
  ),
}));

vi.mock("../components/modals/ModelInfoModal", () => ({
  default: ({ isOpen, modelInfo, onClose }) =>
    isOpen ? (
      <div>
        <span>{`info-modal:${modelInfo.name}`}</span>
        <button onClick={onClose}>close-info</button>
      </div>
    ) : null,
}));

vi.mock("../components/modals/MessageModal", () => ({
  default: ({ isOpen, title, message, type, onClose }) =>
    isOpen ? (
      <div>
        <span>{`${title}: ${message}`}</span>
        <button onClick={onClose}>{`close-${type}`}</button>
      </div>
    ) : null,
}));

vi.mock("../components/modals/WelcomeModal", () => ({
  default: ({ isOpen, onClose }) =>
    isOpen ? <button onClick={onClose}>close-welcome</button> : null,
}));

vi.mock("../components/LoadingPopup", () => ({
  default: ({ show, onClose }) => (show ? <button onClick={onClose}>close-loading</button> : null),
}));

vi.mock("../components/modals/DeleteModelModal", () => ({
  default: ({ isOpen, onConfirm, onCancel }) =>
    isOpen ? (
      <div>
        <button onClick={onConfirm}>confirm-delete</button>
        <button onClick={onCancel}>cancel-delete</button>
      </div>
    ) : null,
}));

import apiClient from "../services/api/client";
import LandingPage from "./LandingPage.jsx";

// Two team-tested, instruct-named base models (certified picks that also
// qualify as flagships -> exercises the recommended-rail dedup) plus one
// community fine-tune.
const remoteModels = [
  {
    id: 101,
    name: "Qwen2.5 7B Instruct",
    is_base: true,
    param_size: 7,
    type: "qwen",
    model_metadata: "size: 4.7 GB",
    link: "q7",
  },
  {
    id: 102,
    name: "Llama 3.1 8B Instruct",
    is_base: true,
    param_size: 8,
    type: "llama",
    model_metadata: "size: 4.9 GB",
    link: "l8",
  },
  {
    id: 103,
    name: "Communo 1B Chat",
    is_base: false,
    param_size: 1,
    model_metadata: "size: 0.7 GB",
    link: "c1",
  },
];

const baseLocal = {
  id: 5,
  name: "base-model",
  link: "org/base",
  model_metadata: "size: 4.2 GB",
  weights_available: true,
  kb_id: null,
};

const orphanAssistant = {
  id: 9,
  name: "kb-helper",
  link: "org/base",
  kb_id: 3,
  weights_available: false,
  model_metadata: null,
};

const hardware = {
  backend_type: "mlx",
  global_inference_score: 82,
  global_inference_label: "Great",
  raw_inference_score: 70,
  recommended_param_min: 1,
  recommended_param_max: 8,
};

const jsonResponse = (payload) => ({ ok: true, status: 200, json: async () => payload });

const routes = { local: [], remote: remoteModels };

const defaultFetch = async (url, opts = {}) => {
  const u = String(url);
  if (opts.method === "DELETE") return jsonResponse({});
  if (opts.method === "POST") return jsonResponse({});
  if (u.endsWith("/llms/local")) return jsonResponse(routes.local);
  if (u.endsWith("/llms/remote")) return jsonResponse(routes.remote);
  if (u.endsWith("/hardware/detailed"))
    return jsonResponse({
      hardware: {
        mlx_chip_model: "M3 Pro",
        total_memory_gb: 36,
        mlx_gpu_cores: 18,
        memory_bandwidth_gbs: 150,
      },
    });
  return jsonResponse([]);
};

const localCalls = () =>
  tracedFetchMock.mock.calls.filter(([u, o]) => String(u).endsWith("/llms/local") && !o?.method);

beforeEach(() => {
  routes.local = [];
  routes.remote = remoteModels;
  ctx.open = vi.fn();
  ctx.completionCount = 0;
  navigateMock.mockReset();
  sectionReloadSpy.mockReset();
  tracedFetchMock.mockReset();
  tracedFetchMock.mockImplementation(defaultFetch);
  apiClient.get.mockReset();
  apiClient.get.mockImplementation(async (path) => {
    if (path === "/startup/welcome-popup") return { has_already_displayed: true };
    if (path === "/hardware/app_startup") return hardware;
    return {};
  });
});
afterEach(() => {
  cleanup();
});

describe("LandingPage explore catalog (#122)", () => {
  it("recommends certified picks once (deduped against flagships) and names the chip", async () => {
    render(<LandingPage />);

    // Both certified instruct models land in the rail exactly once each.
    await waitFor(() => expect(screen.getAllByText("explore:Qwen2.5 7B Instruct")).toHaveLength(1));
    expect(screen.getAllByText("explore:Llama 3.1 8B Instruct")).toHaveLength(1);
    expect(screen.getByText(/run well on your Apple M3 Pro/)).toBeTruthy();
    // The community fine-tune is not part of the rail.
    expect(screen.queryByText("explore:Communo 1B Chat")).toBeNull();
  });

  it("collapses community fine-tunes by default and toggles them open/closed", async () => {
    render(<LandingPage />);

    const toggle = await screen.findByText("Community fine-tunes");
    expect(screen.getByText("Show all")).toBeTruthy();
    expect(screen.queryByText("explore:Communo 1B Chat")).toBeNull();

    fireEvent.click(toggle);
    expect(await screen.findByText("explore:Communo 1B Chat")).toBeTruthy();
    expect(screen.getByText("Hide")).toBeTruthy();

    fireEvent.click(screen.getByText("Community fine-tunes"));
    await waitFor(() => expect(screen.queryByText("explore:Communo 1B Chat")).toBeNull());
  });

  it("opens and closes the model info modal from an explore card", async () => {
    render(<LandingPage />);

    fireEvent.click(await screen.findByText("info:Qwen2.5 7B Instruct"));
    expect(await screen.findByText("info-modal:Qwen2.5 7B Instruct")).toBeTruthy();

    fireEvent.click(screen.getByText("close-info"));
    await waitFor(() => expect(screen.queryByText(/info-modal:/)).toBeNull());
  });

  it("jumps to a section through the explore index", async () => {
    const scrollSpy = vi.fn();
    Element.prototype.scrollIntoView = scrollSpy;
    render(<LandingPage />);

    fireEvent.click(await screen.findByText("jump-search"));

    expect(scrollSpy).toHaveBeenCalledWith({ behavior: "smooth", block: "start" });
    delete Element.prototype.scrollIntoView;
  });
});

describe("LandingPage welcome gate", () => {
  it("shows the welcome modal, gates closing on the running evaluation, then closes", async () => {
    let resolveHardware;
    apiClient.get.mockImplementation((path) => {
      if (path === "/startup/welcome-popup")
        return Promise.resolve({ has_already_displayed: false });
      if (path === "/hardware/app_startup")
        return new Promise((resolve) => (resolveHardware = resolve));
      return Promise.resolve({});
    });
    render(<LandingPage />);

    // Closing while the evaluation still runs opens the loading popup instead.
    fireEvent.click(await screen.findByText("close-welcome"));
    fireEvent.click(await screen.findByText("close-loading"));
    expect(screen.getByText("close-welcome")).toBeTruthy();

    // Once the evaluation lands, the welcome modal closes for real.
    resolveHardware(hardware);
    await waitFor(() => {
      fireEvent.click(screen.getByText("close-welcome"));
      expect(screen.queryByText("close-welcome")).toBeNull();
    });

    // The sidebar logo reopens it on demand.
    const logo = screen.getByAltText("Erudi");
    fireEvent.error(logo); // broken-image handler only logs
    fireEvent.click(logo);
    expect(await screen.findByText("close-welcome")).toBeTruthy();
  });

  it("survives welcome/hardware/machine-detail fetch failures", async () => {
    apiClient.get.mockImplementation(async () => {
      throw new Error("backend down");
    });
    tracedFetchMock.mockImplementation(async (url, opts = {}) => {
      if (String(url).endsWith("/hardware/detailed")) throw new Error("no detail");
      return defaultFetch(url, opts);
    });
    render(<LandingPage />);

    // The page still renders its catalog and no error modal pops up.
    expect(await screen.findByText("explore:Qwen2.5 7B Instruct")).toBeTruthy();
    expect(screen.queryByText(/close-error/)).toBeNull();
  });
});

describe("LandingPage installed list refresh", () => {
  it("surfaces a non-ok refresh in the error modal and closes it", async () => {
    render(<LandingPage />);
    await screen.findByTitle("Refresh installed models");

    tracedFetchMock.mockImplementation(async (url, opts = {}) => {
      if (String(url).endsWith("/llms/local") && !opts.method) return { ok: false, status: 500 };
      return defaultFetch(url, opts);
    });
    fireEvent.click(screen.getByTitle("Refresh installed models"));

    expect(await screen.findByText(/Error: Failed to fetch local models/)).toBeTruthy();
    fireEvent.click(screen.getByText("close-error"));
    await waitFor(() => expect(screen.queryByText(/Error:/)).toBeNull());
  });

  it("surfaces a thrown refresh in the same error modal", async () => {
    render(<LandingPage />);
    await screen.findByTitle("Refresh installed models");

    tracedFetchMock.mockImplementation(async (url, opts = {}) => {
      if (String(url).endsWith("/llms/local") && !opts.method) throw new Error("offline");
      return defaultFetch(url, opts);
    });
    fireEvent.click(screen.getByTitle("Refresh installed models"));

    expect(await screen.findByText(/Error: Failed to fetch local models/)).toBeTruthy();
  });

  it("reloads the main list when the sidebar section asks for a refresh", async () => {
    render(<LandingPage />);
    await screen.findByText("section-refresh");
    const before = localCalls().length;

    fireEvent.click(screen.getByText("section-refresh"));

    await waitFor(() => expect(localCalls().length).toBe(before + 1));
  });

  it("reloads both lists when a download completes anywhere (#205)", async () => {
    ctx.completionCount = 1;
    render(<LandingPage />);

    await waitFor(() => expect(sectionReloadSpy).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(localCalls().length).toBeGreaterThanOrEqual(2));
  });

  it("reloads both lists after a download started from a card completes", async () => {
    render(<LandingPage />);
    fireEvent.click(await screen.findByText("dl:Qwen2.5 7B Instruct"));

    expect(ctx.open).toHaveBeenCalledTimes(1);
    const [model, callbacks] = ctx.open.mock.calls[0];
    expect(model.name).toBe("Qwen2.5 7B Instruct");

    const before = localCalls().length;
    await callbacks.onComplete();
    expect(sectionReloadSpy).toHaveBeenCalledTimes(1);
    expect(localCalls().length).toBe(before + 1);
  });
});

describe("LandingPage local card actions", () => {
  beforeEach(() => {
    routes.local = [baseLocal];
  });

  it("navigates to the knowledge-base attach flow and shows Unknown for broken metadata", async () => {
    routes.local = [{ ...baseLocal, model_metadata: 42 }]; // non-string -> parse fallback
    render(<LandingPage />);
    await screen.findByText("base-model");

    expect(screen.getByText("Size: Unknown")).toBeTruthy();
    fireEvent.click(screen.getByTitle("Knowledge Base"));
    expect(navigateMock).toHaveBeenCalledWith("/erudi/attach_knowledge_base?model=base-model");
    fireEvent.click(screen.getByTitle("Chat"));
    expect(navigateMock).toHaveBeenCalledWith("/erudi/chat?model=base-model");
  });

  it("shows the success modal after a confirmed delete and closes it", async () => {
    render(<LandingPage />);
    await screen.findByText("base-model");

    fireEvent.click(screen.getByTitle("Delete model"));
    fireEvent.click(await screen.findByText("confirm-delete"));

    expect(
      await screen.findByText("Success: Model base-model has been successfully deleted.")
    ).toBeTruthy();
    fireEvent.click(screen.getByText("close-success"));
    await waitFor(() => expect(screen.queryByText(/Success:/)).toBeNull());
    // The sidebar reload runs after the 600ms reload spinner delay.
    await waitFor(() => expect(sectionReloadSpy).toHaveBeenCalled(), { timeout: 2000 });
  });

  it("surfaces a failed delete in the error modal", async () => {
    tracedFetchMock.mockImplementation(async (url, opts = {}) => {
      if (opts.method === "DELETE") return { ok: false, status: 500, json: async () => ({}) };
      return defaultFetch(url, opts);
    });
    render(<LandingPage />);
    await screen.findByText("base-model");

    fireEvent.click(screen.getByTitle("Delete model"));
    fireEvent.click(await screen.findByText("confirm-delete"));

    expect(await screen.findByText(/Error: Failed to delete the model/)).toBeTruthy();
  });

  it("treats a 409 with an unreadable payload as a delete failure", async () => {
    tracedFetchMock.mockImplementation(async (url, opts = {}) => {
      if (opts.method === "DELETE")
        return {
          ok: false,
          status: 409,
          json: async () => {
            throw new Error("bad json");
          },
        };
      return defaultFetch(url, opts);
    });
    render(<LandingPage />);
    await screen.findByText("base-model");

    fireEvent.click(screen.getByTitle("Delete model"));
    fireEvent.click(await screen.findByText("confirm-delete"));

    expect(await screen.findByText(/Error: Failed to delete the model/)).toBeTruthy();
  });
});

describe("LandingPage assistant re-bind (#225)", () => {
  beforeEach(() => {
    routes.local = [baseLocal, orphanAssistant];
  });

  const openPickerAndChoose = async () => {
    render(<LandingPage />);
    await screen.findByText("kb-helper");
    fireEvent.click(screen.getByTitle("Re-bind to another installed model"));
    // The picker entry is a plain div; the base model's card title is an h3.
    const target = screen.getAllByText("base-model").find((el) => el.tagName !== "H3");
    fireEvent.click(target);
  };

  it("POSTs the new base id, shows the success modal and reloads the sidebar", async () => {
    await openPickerAndChoose();

    expect(
      await screen.findByText("Success: kb-helper now uses the weights of base-model.")
    ).toBeTruthy();
    const rebindCall = tracedFetchMock.mock.calls.find(([u]) =>
      String(u).endsWith("/llms/9/rebind")
    );
    expect(rebindCall[1].method).toBe("POST");
    expect(JSON.parse(rebindCall[1].body)).toEqual({ new_base_llm_id: 5 });
    // The sidebar reload runs after the 600ms reload spinner delay.
    await waitFor(() => expect(sectionReloadSpy).toHaveBeenCalled(), { timeout: 2000 });
  });

  it("surfaces a failed re-bind in the error modal", async () => {
    tracedFetchMock.mockImplementation(async (url, opts = {}) => {
      if (String(url).endsWith("/rebind")) return { ok: false, status: 500 };
      return defaultFetch(url, opts);
    });
    await openPickerAndChoose();

    expect(await screen.findByText(/Error: Failed to re-bind the assistant/)).toBeTruthy();
  });
});
