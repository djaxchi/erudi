// Sidebar.jsx
import React from "react";
import { Brain, MessageSquare } from "lucide-react";
import { NavLink } from "react-router-dom";  // ⬅️  make sure react-router-dom v6+

function SidebarIcon({ to, Icon }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        `w-full flex justify-center items-center py-4
         ${isActive ? "border-l-4 border-green-500" : ""}
        `
      }
    >
      {({ isActive }) => (
        <Icon
          className={`w-6 h-6 ${
            isActive ? "text-green-400" : "text-gray-400"
          }`}
        />
      )}
    </NavLink>
  );
}

export default function Sidebar() {
  return (
    <div className="w-16 bg-[#121212] flex flex-col items-center">
      <SidebarIcon to="/main_window/models" Icon={Brain} />
      <SidebarIcon to="/main_window/chat"   Icon={MessageSquare} />
    </div>
  );
}
