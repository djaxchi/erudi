import React from "react";
import PropTypes from "prop-types";
import { useState, useRef, useEffect } from "react";
import { ChevronDown } from "lucide-react";

export default function Dropdown({ options, value, onChange }) {
  const [open, setOpen] = useState(false);
  const ref = useRef();

  // close when clicking outside
  useEffect(() => {
    function onClick(e) {
      if (ref.current && !ref.current.contains(e.target)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  return (
    <div ref={ref} className="relative inline-block w-48 text-sm">
      {/* Button */}
      <button
        type="button"
        className="w-full bg-transparent border border-gray-400 rounded-full px-4 py-2 pr-8 text-white flex justify-between items-center focus:border-emerald-400/50 focus:ring-0 focus:outline-none"
        onClick={() => setOpen((o) => !o)}
      >
        {value}
        <ChevronDown className="w-4 h-4 text-gray-300 pointer-events-none" />
      </button>

      {/* Options */}
      {open && (
        <ul className="absolute left-0 right-0 bg-gray-800 text-white rounded-xl shadow-lg max-h-60 overflow-auto z-20 ">
          {options.map((opt) => (
            <li
              key={opt}
              className={`cursor-pointer px-4 py-2 hover:bg-gray-600 ${
                opt === value ? "font-semibold text-emerald-400" : "font-normal"
              }`}
              onClick={() => {
                onChange(opt);
                setOpen(false);
              }}
            >
              {opt}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

Dropdown.propTypes = {
  options: PropTypes.arrayOf(PropTypes.string).isRequired,
  value: PropTypes.string.isRequired,
  onChange: PropTypes.func.isRequired,
};
