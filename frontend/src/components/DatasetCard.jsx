import React, { useState, useRef } from "react";
import DragDropArea from "./DragDropArea";
import Dropdown from "./Dropdown";
import { Check, Folder } from "lucide-react";

const API_BASE = "http://localhost:8000";


export default function DatasetCard({ selectedModel, modelName }) {
  const [type, setType] = useState("Textuel");
  const types = ["Textuel", "Images", "Audio"];

  const [dataPath, setDataPath] = useState("/AppData/DataStorage/");
  const [paths, setPaths] = useState([]);

  const fileInputRef = useRef(null);
  const [errorMsg, setErrorMsg] = useState("");

  const openExplorer = () => {
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
      fileInputRef.current.click();
    }
  };

  const onFilesChosen = (e) => {
    const files = Array.from(e.target.files || []);
    if (files.length === 0) return;

    const folderSet = new Set(paths);

    files.forEach((file) => {
      const rel = file.webkitRelativePath || file.name;
      const rootDir = rel.split("/")[0];
      folderSet.add(rootDir);
    });

    const updated = Array.from(folderSet);
    setPaths(updated);

    setDataPath(
      updated.length === 1 ? `…/${updated[0]}` : `…/${updated.length} folders`
    );
  };

  const submitTrainForm = async () => {
    setErrorMsg("");

    if (!selectedModel) {
      setErrorMsg("Please select a model to train.");
      return;
    }
    if (!modelName || modelName.trim() === "") {
      setErrorMsg("Please name your new model.");
      return;
    }
    if (paths.length === 0) {
      setErrorMsg("Please select at least one folder.");
      return;
    }

    try {
      const response = await fetch(`${API_BASE}/upload-folders`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          paths: paths,
          selectedModel: selectedModel,
          modelName: modelName,
        }),
      });

      if (!response.ok) {
        throw new Error("Erreur lors de l'envoi des infos d'entrainement");
      }

      const data = await response.json();
      console.log("Réponse du backend:", data);
    } catch (error) {
      console.error("Erreur lors de l'envoi des infos d'entrainement:", error);
      setErrorMsg("Une erreur est survenue.");
    }
  };

  return (
    <div className="flex-1 bg-[#2B2B2B] rounded-2xl p-8 text-white flex flex-row gap-6 shadow-lg justify-center items-center">
      <div className="flex flex-col justify-center items-center gap-6 w-[50%]">
        <div className="flex flex-row gap-8 w-full">
          <div className="flex flex-col gap-2 w-30">
            <div>
              <h3 className="text-xl font-bold mb-4">Dataset Type</h3>
              <Dropdown options={types} value={type} onChange={setType} />
            </div>

            <h3 className="text-xl font-bold mb-2">Data Path</h3>
            <input
              readOnly
              value={dataPath}
              onClick={openExplorer}
              className="w-full bg-transparent border border-gray-400 rounded-full px-4 py-2 text-sm truncate max-w-[190px] cursor-pointer focus:border-emerald-400/50 focus:ring-0 focus:outline-none"
              placeholder="Click to specify path"
            />

            <input
              type="file"
              multiple
              ref={fileInputRef}
              className="hidden"
              webkitdirectory="true"
              directory="true"
              onChange={onFilesChosen}
            />
          </div>

          <div className="flex flex-col gap-1 w-[50%]">
            <h3 className="text-xl font-bold mb-2">Dataset</h3>
            <div
              className="bg-gray-800/50 rounded-lg p-4 overflow-y-auto h-36 mt-2 shadow-lg"
              style={{ scrollbarWidth: "none", msOverflowStyle: "none" }}
            >
              <ul className="space-y-2 text-white/80 text-sm">
                {paths.length === 0 ? (
                  <li className="italic text-white/60">Add Folders...</li>
                ) : (
                  paths.map((p) => (
                    <li key={p} className="flex items-center gap-2">
                      <Folder className="w-5 h-5" />
                      <span className="truncate flex-1">{p}</span>
                      <Check className="w-5 h-5 text-emerald-400" />
                    </li>
                  ))
                )}
              </ul>
            </div>
          </div>
        </div>

        <div className="flex-1 flex items-end">
          <button className="w-40 mx-auto py-3 rounded-full border border-emerald-400/20 text-emerald-400 font-semibold hover:bg-emerald-400/10 transition"
            onClick={submitTrainForm}
          >
            Train
          </button>
          {errorMsg && (
            <div className="text-red-400 text-sm mt-2 text-center w-full">{errorMsg}</div>
          )}
        </div>
      </div>

      <div className="w-[50%] rounded-2xl flex flex-col gap-6 shadow-lg">
        <DragDropArea />
      </div>
    </div>
  );
}
