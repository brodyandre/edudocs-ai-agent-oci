import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#17202a",
        paper: "#f8faf7",
        line: "#d8e0d6",
        pine: "#245347",
        teal: "#1f766d",
        amber: "#b7791f",
        rose: "#b4233c",
      },
      boxShadow: {
        soft: "0 16px 50px rgba(23, 32, 42, 0.08)",
      },
    },
  },
  plugins: [],
};

export default config;
