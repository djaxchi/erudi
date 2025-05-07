import React from "react";
import SidebarIcon from "./SidebarIcon";
import { Brain, MessageSquare } from "lucide-react";

export default function Sidebar() {
  return (
    <div className="w-16 bg-[#121212] flex flex-col items-center">
      <SidebarIcon active>
        <Brain className="w-6 h-6 text-green-400" />
      </SidebarIcon>
      <SidebarIcon>
        <MessageSquare className="w-6 h-6 text-gray-400" />
      </SidebarIcon>
    </div>
  );
}