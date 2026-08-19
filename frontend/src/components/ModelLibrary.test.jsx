// @vitest-environment jsdom
import React from "react";
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import ModelLibrary from "./ModelLibrary";

const models = [
  { id: "m1", name: "Gemma 2 2B", type: "text" },
  { id: "m2", name: "Qwen3 4B" },
];

afterEach(cleanup);

describe("ModelLibrary", () => {
  it("shows an empty state when there are no local models", () => {
    render(<ModelLibrary models={[]} />);
    expect(screen.getByText("No local LLMs found.")).toBeTruthy();
  });

  it("lists models with their type and reports clicks", () => {
    const onModelSelect = vi.fn();
    render(<ModelLibrary models={models} onModelSelect={onModelSelect} />);
    expect(screen.getByText("text")).toBeTruthy();
    fireEvent.click(screen.getByText("Qwen3 4B"));
    expect(onModelSelect).toHaveBeenCalledWith("m2");
  });

  it("highlights the selected model", () => {
    render(<ModelLibrary models={models} selectedModel="m1" onModelSelect={() => {}} />);
    const selected = screen.getByText("Gemma 2 2B").closest("div[class*='cursor-pointer']");
    expect(selected.className).toContain("border-emerald-400/30");
  });

  it("invokes onRefresh from the refresh icon", () => {
    const onRefresh = vi.fn();
    render(<ModelLibrary models={models} onRefresh={onRefresh} />);
    fireEvent.click(screen.getByTitle("Refresh models"));
    expect(onRefresh).toHaveBeenCalledTimes(1);
  });

  it("keeps the name input disabled until a model is selected", () => {
    render(<ModelLibrary models={models} selectedModel={null} />);
    expect(screen.getByPlaceholderText("Select a model first").disabled).toBe(true);
  });

  it("locks a trimmed name and unlocks back to editable", () => {
    const onModelNameChange = vi.fn();
    render(
      <ModelLibrary
        models={models}
        selectedModel="m1"
        modelName="my-model"
        onModelNameChange={onModelNameChange}
      />
    );
    const input = screen.getByPlaceholderText("Enter model name...");
    const button = screen.getByTitle("Validate and lock name");
    expect(button.disabled).toBe(true); // empty name cannot be locked
    fireEvent.change(input, { target: { value: "  my-model  " } });
    fireEvent.click(button);
    expect(onModelNameChange).toHaveBeenCalledWith("my-model");
    expect(input.readOnly).toBe(true);
    fireEvent.click(screen.getByTitle("Cancel and unlock"));
    expect(onModelNameChange).toHaveBeenLastCalledWith("");
    expect(input.readOnly).toBe(false);
  });
});
