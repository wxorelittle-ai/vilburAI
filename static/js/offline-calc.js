/* Офлайн-калькулятор себестоимости (раздел 7.5 ТЗ) — те же формулы, что на сервере.
   Работает без интернета: чистый JS на фронтенде. */
(function () {
  'use strict';

  function num(id) {
    var el = document.getElementById(id);
    var v = parseFloat((el && el.value || '').replace(',', '.'));
    return isNaN(v) ? 0 : v;
  }
  function money(x) {
    return (Math.round(x * 100) / 100).toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  function compute() {
    var ploshad = num('c_ploshad');
    var rabochih = num('c_rabochih');
    var dni = num('c_dni');
    var stavka = num('c_stavka');
    var arenda = num('c_arenda');
    var dostavka = num('c_dostavka');
    var rashodniki = num('c_rashodniki');
    var nalogSel = document.getElementById('c_nalog');
    var nalog = nalogSel ? parseFloat(nalogSel.value) / 100 : 0;

    var trud = rabochih * dni * stavka;
    var post = arenda + dostavka + rashodniki;
    var sebe = trud + post;
    var sebeM2 = ploshad ? sebe / ploshad : 0;
    var denom = nalog < 1 ? 1 - nalog : 1;
    var cena30 = (sebe * 1.3) / denom;
    var cena50 = (sebe * 1.5) / denom;

    var out = document.getElementById('c_result');
    if (!out) return;
    out.innerHTML =
      '<div class="row floor"><span>Себестоимость за м²</span><b>' + money(sebeM2) + ' ₽</b></div>' +
      '<div class="row"><span>Себестоимость всего</span><b>' + money(sebe) + ' ₽</b></div>' +
      '<div class="row"><span>Цена +30% прибыли</span><b>' + money(ploshad ? cena30 / ploshad : 0) + ' ₽/м²</b></div>' +
      '<div class="row"><span>Цена +50% прибыли</span><b>' + money(ploshad ? cena50 / ploshad : 0) + ' ₽/м²</b></div>';
    out.style.display = 'block';
  }

  window.addEventListener('DOMContentLoaded', function () {
    var btn = document.getElementById('c_calc');
    if (btn) btn.addEventListener('click', compute);
  });
})();
