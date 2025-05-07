import React from "react";
import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import LandingPage from "./pages/LandingPage";
import LocalModelsPage from "./pages/LocalModelsPage";
import AvailableModelsPage from "./pages/AvailableModelsPage";
import TrainNewModelPage from "./pages/TrainNewModelPage";

export default function App() {
  return (
    <Router>
      <Routes>
        <Route path="/main_window" element={<LandingPage />} />
        <Route path="/main_window/local-models" element={<LocalModelsPage />} />
        <Route path="/main_window/available-models" element={<AvailableModelsPage />} />
        <Route path="/main_window/train-new-model" element={<TrainNewModelPage />} />
      </Routes>
    </Router>
  );
}