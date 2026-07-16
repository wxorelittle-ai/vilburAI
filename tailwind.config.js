/** Конфиг Tailwind для сборки статического CSS (см. static/css/app.css).
 *  Пересобрать после правки шаблонов:
 *    npx tailwindcss@3 -c tailwind.config.js -i static/css/tailwind.src.css -o static/css/app.css --minify
 *  Раньше стили собирались в браузере через Play CDN — это тормозило загрузку
 *  и ломало офлайн-режим PWA (раздел 7.5 ТЗ). Теперь CSS собран заранее.
 */
module.exports = {
  content: ['./templates/**/*.html', './static/js/**/*.js'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        display: ['Manrope', 'Inter', 'sans-serif'],
      },
      colors: {
        // Фирменная палитра Вильбур AI
        grafit: '#262421',
        terracotta: '#C1502E',
        sand: '#F3EDE4',
        steel: '#6B6862',
        amber: '#D89A54',
        'sand-deep': '#E7DDCE',
        'grafit-700': '#33302B',
        // Легаси-алиасы (используются в шаблонах)
        navy: '#262421',
        accent: '#C1502E',
        'accent-dark': '#A23F22',
      },
      boxShadow: {
        card: '0 1px 2px rgba(38,36,33,.04), 0 8px 24px -12px rgba(38,36,33,.18)',
        lift: '0 10px 30px -12px rgba(38,36,33,.35)',
      },
      borderRadius: { '2xl': '1.1rem' },
    },
  },
  plugins: [],
};
