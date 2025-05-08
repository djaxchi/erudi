import React from "react";
import { BrowserRouter as Router, Routes, Route, Navigate } from "react-router-dom";
import LandingPage from "./pages/LandingPage";

export default function App() {
  return (
    <Router>
      <Routes>
        <Route path="/main_window" element={<LandingPage />} />
      </Routes>
    </Router>
  );
}