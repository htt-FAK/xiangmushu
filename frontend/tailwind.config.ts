import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        night: {
          950: "#05060a",
          900: "#090d14",
          850: "#0d131d",
          800: "#111a25",
          700: "#172332",
        },
        signal: {
          cyan: "#36f2e6",
          lime: "#b8ff5e",
          amber: "#ffb84d",
          rose: "#ff4d8d",
        },
      },
      fontFamily: {
        sans: [
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "Microsoft YaHei",
          "PingFang SC",
          "sans-serif",
        ],
        display: [
          "Rajdhani",
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "Microsoft YaHei",
          "sans-serif",
        ],
      },
      boxShadow: {
        panel: "0 18px 60px rgba(5, 6, 10, 0.5)",
        glow: "0 0 0 1px rgba(54, 242, 230, 0.18), 0 0 20px rgba(54, 242, 230, 0.12)",
      },
    },
  },
  plugins: [],
};

export default config;
