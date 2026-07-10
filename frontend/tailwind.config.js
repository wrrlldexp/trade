/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        // Цвета подхватываются из CSS-переменных, которые
        // адаптер авторизации заполняет под нативную тему Telegram/VK
        bg: "var(--tg-theme-bg-color, #ffffff)",
        text: "var(--tg-theme-text-color, #000000)",
        hint: "var(--tg-theme-hint-color, #707579)",
        link: "var(--tg-theme-link-color, #2481cc)",
        button: "var(--tg-theme-button-color, #2481cc)",
        "button-text": "var(--tg-theme-button-text-color, #ffffff)",
        secondary: "var(--tg-theme-secondary-bg-color, #f1f1f1)",
      },
      fontFamily: {
        sans: [
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "Roboto",
          "Helvetica",
          "Arial",
          "sans-serif",
        ],
      },
    },
  },
  plugins: [],
};
