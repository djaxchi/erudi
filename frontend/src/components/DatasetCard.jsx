import React, { useState, useRef, useEffect } from "react";
import DragDropArea from "./DragDropArea";
import Dropdown from "./Dropdown";
import { Check, Folder, Loader } from "lucide-react";

const API_BASE = "http://localhost:8000";


export default function DatasetCard({ selectedModel, modelName }) {
  const [type, setType] = useState("Textuel");
  const types = ["Textuel", "Images", "Audio"];

  const [dataPath, setDataPath] = useState("/AppData/DataStorage/");
  const [paths, setPaths] = useState([]);
  
  // Nouveaux états pour le suivi d'entraînement
  const [isTraining, setIsTraining] = useState(false);
  const [trainingStatus, setTrainingStatus] = useState(null);
  const [trainingError, setTrainingError] = useState("");
  const [trainingId, setTrainingId] = useState(null);
  const pollingRef = useRef(null);

  const fileInputRef = useRef(null);
  const [errorMsg, setErrorMsg] = useState("");

  // Effet pour nettoyer l'interval de polling lorsque le composant est démonté
  useEffect(() => {
    return () => {
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
      }
    };
  }, []);

  const openExplorer = async () => {
    
    if (window.electron) {
      const selectedPath = await window.electron.openDirectory();
      if (selectedPath) {
        setDataPath(selectedPath);
        paths.push(selectedPath);
        console.log("Chemin du dossier sélectionné :", selectedPath);
      }
    } else {
      console.error('window.electron est undefined');
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
    console.log("Selected folders:", updated);

    setDataPath(
      updated.length === 1 ? `…/${updated[0]}` : `…/${updated.length} folders`
    );
  };

  const [progress, setProgress] = useState(0);
  const [timeElapsed, setTimeElapsed] = useState(0);
  const [timeLeft, setTimeLeft] = useState(null);
  const checkTrainingStatus = async (llmId) => {
    try {
      const response = await fetch(`${API_BASE}/training/${llmId}/status`);
      
      if (!response.ok) {
        if (response.status === 404) {
          // Le job de training n'existe plus (probablement supprimé après un échec)
          setTrainingError("Le job d'entraînement n'existe plus ou a échoué.");
          setIsTraining(false);
          return true; // Arrêter le polling
        }
        throw new Error(`Erreur HTTP ${response.status}`);
      }

      const data = await response.json();

      setTrainingStatus(data.status);
      setProgress(data.progress || 0);
      setTimeElapsed(data.time_elapsed || 0);
      setTimeLeft(data.time_left);

      // Traitement selon le statut
      if (data.status === "failed") {
        setTrainingError(data.error_message || "L'entraînement a échoué.");
        setIsTraining(false);
        return true; // Arrêter le polling
      } else if (data.status === "completed") {
        setTrainingError("");
        setIsTraining(false);
        return true; // Arrêter le polling
      }

      // Continuer le polling pour "pending" ou "running"
      return false;
    } catch (error) {
      console.error("Erreur lors de la vérification du statut:", error);
      setTrainingError(`Erreur lors de la vérification du statut: ${error.message}`);
      setIsTraining(false);
      return true; // Arrêter le polling en cas d'erreur
    }
  };

  // Fonction pour démarrer le polling
  const startPolling = (llmId) => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
    }

    // Vérifier toutes les 3 secondes
    pollingRef.current = setInterval(async () => {
      const shouldStop = await checkTrainingStatus(llmId);
      
      if (shouldStop && pollingRef.current) {
        clearInterval(pollingRef.current);
        pollingRef.current = null;
      }
    }, 1000);
  };

  const submitTrainForm = async () => {
    setErrorMsg("");
    setTrainingError("");

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
      // Activer l'état d'entraînement
      setIsTraining(true);
      setTrainingStatus("pending");
      
      const response = await fetch(`${API_BASE}/train`, {
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
        throw new Error("Erreur provenant du backend");
      }

      const data = await response.json();
      console.log("Réponse du backend:", data);
      
      // Récupérer l'ID du modèle en entraînement et démarrer le polling
      if (data.llm_in_training_id) {
        setTrainingId(data.llm_in_training_id);
        startPolling(data.llm_in_training_id);
      } else {
        throw new Error("ID du modèle en entraînement non reçu");
      }
      
    } catch (error) {
      console.error("Erreur lors de l'envoi des infos d'entrainement:", error);
      setErrorMsg("Une erreur est survenue.");
      setIsTraining(false);
    }
  };

  return (
    <div className="flex-1 bg-[#2B2B2B] rounded-2xl p-8 text-white flex flex-row gap-6 shadow-lg justify-center items-center">
      <div className="flex flex-col justify-center items-center gap-6 w-[50%]">
        <div className="flex flex-row justify-center gap-8 lg:gap-24 w-full h-[80%]">
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

        <div className="flex-1 flex lg:mt-12 items-end flex-col">
          {isTraining ? (
            <div className="w-full text-center">
              <div className="w-full bg-gray-700 rounded-full h-4 mb-2">
                <div
                  className="bg-emerald-400 h-4 rounded-full transition-all"
                  style={{ width: `${progress}%` }}
                ></div>
              </div>
              <div className="text-emerald-400 text-sm">
                {progress.toFixed(1)}% — 
                {timeElapsed ? ` Écoulé: ${Math.round(timeElapsed)}s` : ""}
                {timeLeft ? ` — Restant: ~${Math.round(timeLeft)}s` : ""}
              </div>
              <div className="inline-flex items-center gap-2 py-3">
                <Loader className="w-5 h-5 text-emerald-400 animate-spin" />
                <span className="text-emerald-400">
                  {trainingStatus === "running"
                    ? "Entraînement en cours..."
                    : "Préparation de l'entraînement..."}
                </span>
              </div>
            </div>
          ) : (
            <button 
              className="w-40 mx-auto py-3 rounded-full border border-emerald-400/20 text-emerald-400 font-semibold hover:bg-emerald-400/10 transition"
              onClick={submitTrainForm}
            >
              Train
            </button>
          )}
        </div>
        
        {errorMsg && (
          <div className="text-red-400 text-sm mt-2 text-center w-full">{errorMsg}</div>
        )}
        
        {trainingError && (
          <div className="text-red-400 text-sm mt-2 text-center w-full">{trainingError}</div>
        )}
        
        {trainingStatus === "completed" && (
          <div className="text-emerald-400 text-sm mt-2 text-center w-full">
            Entraînement terminé avec succès!
          </div>
        )}
      </div>

      <div className="w-[50%] h-[80%] rounded-2xl flex flex-col gap-6 shadow-lg">
        <DragDropArea />
      </div>
    </div>
  );
}