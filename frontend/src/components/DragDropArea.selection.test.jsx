// @vitest-environment jsdom
import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent, waitFor } from "@testing-library/react";
import DragDropArea from "./DragDropArea.jsx";

// Selection-management surface of DragDropArea, complementing the folder-drop
// pipeline pinned in DragDropArea.test.jsx: the picker buttons in both empty
// and filled states, per-file removal, drag highlight, the non-Electron
// file.path fallback, unreadable entries, and the Folder badge.

const makeFile = (name) => new File(["content"], name, { type: "" });
const makeFileEntry = (file) => ({
  isFile: true,
  isDirectory: false,
  name: file.name,
  file: (success) => success(file),
});
const makeItem = (entry) => ({ kind: "file", webkitGetAsEntry: () => entry });

const dropZone = (container) => container.querySelector("[data-drag-drop-area]");

const addOneFile = async (container, onFilesAdded, name = "doc.pdf") => {
  fireEvent.drop(dropZone(container), {
    dataTransfer: { items: undefined, files: [makeFile(name)] },
  });
  await waitFor(() => expect(onFilesAdded).toHaveBeenCalled());
};

beforeEach(() => {
  window.electron = { getFilePath: vi.fn((file) => `/abs/${file.name}`) };
});

afterEach(() => {
  cleanup();
  delete window.electron;
  vi.restoreAllMocks();
});

describe("DragDropArea picker buttons", () => {
  it("opens the file picker from the empty-state Browse button and the zone itself", async () => {
    const clickSpy = vi.spyOn(HTMLInputElement.prototype, "click").mockImplementation(() => {});
    const { container } = render(<DragDropArea onFilesAdded={vi.fn()} />);

    fireEvent.click(screen.getByText("Browse files"));
    expect(clickSpy).toHaveBeenCalledTimes(1);

    fireEvent.click(dropZone(container));
    expect(clickSpy).toHaveBeenCalledTimes(2);
  });

  it("opens the folder picker from the empty-state folder button", () => {
    const clickSpy = vi.spyOn(HTMLInputElement.prototype, "click").mockImplementation(() => {});
    render(<DragDropArea onFilesAdded={vi.fn()} />);

    fireEvent.click(screen.getByText("or select a folder"));
    expect(clickSpy).toHaveBeenCalledTimes(1);
  });

  it("offers Add More and Add Folder once files are selected", async () => {
    const onFilesAdded = vi.fn();
    const { container } = render(<DragDropArea onFilesAdded={onFilesAdded} />);
    await addOneFile(container, onFilesAdded);

    expect(screen.getByText("Selected Files (1)")).toBeTruthy();
    const clickSpy = vi.spyOn(HTMLInputElement.prototype, "click").mockImplementation(() => {});
    fireEvent.click(screen.getByText("Add More"));
    expect(clickSpy).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByText("Add Folder"));
    expect(clickSpy).toHaveBeenCalledTimes(2);
  });
});

describe("DragDropArea file removal", () => {
  it("removes a file and reports the reduced list to the parent", async () => {
    const onFilesAdded = vi.fn();
    const { container } = render(<DragDropArea onFilesAdded={onFilesAdded} />);

    fireEvent.drop(dropZone(container), {
      dataTransfer: { items: undefined, files: [makeFile("a.pdf"), makeFile("b.txt")] },
    });
    await waitFor(() => expect(onFilesAdded).toHaveBeenCalledWith(["/abs/a.pdf", "/abs/b.txt"]));

    const [removeFirst] = screen.getAllByLabelText("Remove file");
    fireEvent.click(removeFirst);

    expect(onFilesAdded).toHaveBeenLastCalledWith(["/abs/b.txt"]);
    expect(screen.getByText("Selected Files (1)")).toBeTruthy();
    expect(screen.queryByText("a.pdf")).toBeNull();
  });
});

describe("DragDropArea duplicate handling", () => {
  it("drops a file already in the list instead of counting it twice", async () => {
    // The submission de-duplicates by path, so a second copy in the list is an
    // entry that will never be ingested: the header read "Selected Files (3)"
    // over two distinct files while the confirmation said "2 files" (#350).
    const onFilesAdded = vi.fn();
    const { container } = render(<DragDropArea onFilesAdded={onFilesAdded} />);

    fireEvent.drop(dropZone(container), {
      dataTransfer: { items: undefined, files: [makeFile("a.pdf"), makeFile("b.txt")] },
    });
    await waitFor(() => expect(onFilesAdded).toHaveBeenCalledWith(["/abs/a.pdf", "/abs/b.txt"]));

    fireEvent.drop(dropZone(container), {
      dataTransfer: { items: undefined, files: [makeFile("a.pdf")] },
    });

    await waitFor(() => expect(screen.getByText(/already in the list/)).toBeTruthy());
    expect(screen.getByText("Selected Files (2)")).toBeTruthy();
    expect(screen.getAllByText("a.pdf")).toHaveLength(1);
    expect(onFilesAdded).toHaveBeenLastCalledWith(["/abs/a.pdf", "/abs/b.txt"]);
  });

  it("still adds the new files when a batch mixes fresh and duplicate paths", async () => {
    const onFilesAdded = vi.fn();
    const { container } = render(<DragDropArea onFilesAdded={onFilesAdded} />);

    await addOneFile(container, onFilesAdded, "a.pdf");

    fireEvent.drop(dropZone(container), {
      dataTransfer: { items: undefined, files: [makeFile("a.pdf"), makeFile("c.md")] },
    });

    await waitFor(() => expect(onFilesAdded).toHaveBeenLastCalledWith(["/abs/a.pdf", "/abs/c.md"]));
    expect(screen.getByText("Selected Files (2)")).toBeTruthy();
  });
});

describe("DragDropArea drag highlight", () => {
  it("highlights on drag enter and clears when the drag leaves", () => {
    const { container } = render(<DragDropArea onFilesAdded={vi.fn()} />);
    const zone = dropZone(container);

    fireEvent.dragOver(zone, { dataTransfer: {} });
    fireEvent.dragEnter(zone, { dataTransfer: {} });
    expect(zone.className).toContain("border-emerald-400");

    fireEvent.dragLeave(zone, { dataTransfer: {} });
    expect(zone.className).not.toContain("border-emerald-400");
  });
});

describe("DragDropArea path resolution and badges", () => {
  it("falls back to file.path when no Electron bridge is present", async () => {
    delete window.electron;
    const onFilesAdded = vi.fn();
    const { container } = render(<DragDropArea onFilesAdded={onFilesAdded} />);

    const file = makeFile("report.pdf");
    Object.defineProperty(file, "path", { value: "/home/me/report.pdf" });
    fireEvent.drop(dropZone(container), { dataTransfer: { items: undefined, files: [file] } });

    await waitFor(() => expect(onFilesAdded).toHaveBeenCalledWith(["/home/me/report.pdf"]));
  });

  it("labels an extension-less path as a Folder", async () => {
    window.electron.getFilePath = vi.fn(() => "/abs/my-notes-folder");
    const onFilesAdded = vi.fn();
    const { container } = render(<DragDropArea onFilesAdded={onFilesAdded} />);
    await addOneFile(container, onFilesAdded, "notes.txt");

    expect(screen.getByText("Folder")).toBeTruthy();
    expect(screen.getByText("my-notes-folder")).toBeTruthy();
  });
});

describe("DragDropArea unreadable entries", () => {
  it("skips a file entry whose read fails and keeps the rest", async () => {
    const onFilesAdded = vi.fn();
    const { container } = render(<DragDropArea onFilesAdded={onFilesAdded} />);

    const broken = {
      isFile: true,
      isDirectory: false,
      name: "broken.pdf",
      file: (_success, error) => error(new Error("io")),
    };
    fireEvent.drop(dropZone(container), {
      dataTransfer: { items: [makeItem(broken), makeItem(makeFileEntry(makeFile("ok.pdf")))] },
    });

    await waitFor(() => expect(onFilesAdded).toHaveBeenCalledWith(["/abs/ok.pdf"]));
  });

  it("treats a directory whose listing fails as empty and ignores unknown entry kinds", async () => {
    const onFilesAdded = vi.fn();
    const { container } = render(<DragDropArea onFilesAdded={onFilesAdded} />);

    const failingDir = {
      isFile: false,
      isDirectory: true,
      createReader: () => ({ readEntries: (_success, error) => error(new Error("denied")) }),
    };
    const alien = { isFile: false, isDirectory: false };
    fireEvent.drop(dropZone(container), {
      dataTransfer: {
        items: [
          makeItem(failingDir),
          makeItem(alien),
          makeItem(makeFileEntry(makeFile("kept.md"))),
        ],
      },
    });

    await waitFor(() => expect(onFilesAdded).toHaveBeenCalledWith(["/abs/kept.md"]));
  });
});
