import React, { useEffect, useState } from "react";

export default function App() {
  const [message, setMessage] = useState("Loading...");

  useEffect(() => {
    // Fetch data from the FastAPI backend
    fetch("http://127.0.0.1:8000/ping")
      .then((response) => response.json())
      .then((data) => {
        setMessage(data.message); // Set the message from the backend
      })
      .catch((error) => {
        console.error("Error fetching data:", error);
        setMessage("Error connecting to backend");
      });
  }, []);

  return (
    <div className="min-h-screen max-h-full bg-zinc-950 flex items-center justify-center">
      <div className="font-bold text-white text-2xl">{message}</div>
    </div>
  );
}