import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#0d1412",
        panel: "#141d1a",
        panelSoft: "#19231f",
        paper: "#e9eee9",
        muted: "#9eaaa4",
        line: "#2a3531",
        pine: "#a7f3c2",
        teal: "#6ee7a9",
        amber: "#e6c878",
        rose: "#ff816f",
      },
      boxShadow: {
        soft: "0 28px 90px rgba(0, 0, 0, 0.24)",
      },
    },
  },
  plugins: [],
};

export default config;
