import React from 'react';

export default function LoadingScreen() {
  return (
    <div 
      className="fixed top-0 left-0 w-screen h-screen flex flex-col justify-center items-center z-[9999]"
      style={{ backgroundColor: '#02130e' }}
    >
      <h1 
        className="text-5xl font-extrabold m-0"
        style={{ color: '#00c978' }}
      >
        Erudi
      </h1>
      <p 
        className="text-xl mt-1 mb-8"
        style={{ color: '#e0e0e0' }}
      >
        local fine tuning
      </p>
      <div className="w-12 h-12 border-4 border-gray-200/20 border-t-gray-200/80 rounded-full animate-spin">
      </div>
    </div>
  );
}