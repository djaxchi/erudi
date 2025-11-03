import React from "react";
import PropTypes from "prop-types";

export default function LoadingScreen() {
  return (
    <div
      className="fixed top-0 left-0 w-screen h-screen flex flex-col justify-center items-center z-[9999]"
      style={{ backgroundColor: "#02130e" }}
    >
      <img
        src={require("../img/logoerudifinal.png")}
        alt="erudi Logo"
        className="mb-2 object-contain"
        style={{ maxWidth: "14rem", maxHeight: "14rem" }}
      />
      <p className="text-xl mt-1 mb-8" style={{ color: "#e0e0e0" }}>
        AI with you, for you
      </p>
      <div className="w-12 h-12 border-4 border-gray-200/20 border-t-gray-200/80 rounded-full animate-spin"></div>
    </div>
  );
}
LoadingScreen.propTypes = {};
