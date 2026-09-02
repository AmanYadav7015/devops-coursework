import React from "react";

export default function App() {
  return (
    <div className="app">
      <h1>Hello World</h1>
      <p>
        Rendered by a real <strong>React</strong> component tree (React{" "}
        {React.version}), bundled with esbuild and served as static files by
        nginx:alpine.
      </p>
    </div>
  );
}
