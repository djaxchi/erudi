import React, { useState } from "react";

export default function Tooltip({ children, content, position = "top" }) {
    const [isVisible, setIsVisible] = useState(false);

    const getPositionClasses = () => {
        switch (position) {
            case "top":
                return "bottom-full left-1/2 transform -translate-x-1/2 mb-2";
            case "bottom":
                return "top-full left-1/2 transform -translate-x-1/2 mt-2";
            case "left":
                return "right-full top-1/2 transform -translate-y-1/2 mr-2";
            case "right":
                return "left-full top-1/2 transform -translate-y-1/2 ml-2";
            default:
                return "bottom-full left-1/2 transform -translate-x-1/2 mb-2";
        }
    };

    const getArrowClasses = () => {
        switch (position) {
            case "top":
                return "top-full left-1/2 transform -translate-x-1/2 border-l-transparent border-r-transparent border-b-transparent border-t-gray-800";
            case "bottom":
                return "bottom-full left-1/2 transform -translate-x-1/2 border-l-transparent border-r-transparent border-t-transparent border-b-gray-800";
            case "left":
                return "left-full top-1/2 transform -translate-y-1/2 border-t-transparent border-b-transparent border-r-transparent border-l-gray-800";
            case "right":
                return "right-full top-1/2 transform -translate-y-1/2 border-t-transparent border-b-transparent border-l-transparent border-r-gray-800";
            default:
                return "top-full left-1/2 transform -translate-x-1/2 border-l-transparent border-r-transparent border-b-transparent border-t-gray-800";
        }
    };

    return (
        <div 
            className="relative inline-block"
            onMouseEnter={() => setIsVisible(true)}
            onMouseLeave={() => setIsVisible(false)}
        >
            {children}
            {isVisible && (
                <div className={`absolute z-50 ${getPositionClasses()}`}>
                    <div className="bg-gray-800 text-white text-sm rounded-lg px-4 py-3 w-80 shadow-lg border border-gray-600">
                        {content}
                    </div>
                    {/* Arrow */}
                    <div className={`absolute w-0 h-0 border-4 ${getArrowClasses()}`}></div>
                </div>
            )}
        </div>
    );
}
