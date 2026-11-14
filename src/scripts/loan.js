import { $, load, save } from './lib.js';

const IDS = ['l-amt', 'l-rate', 'l-course', 'l-term', 'l-mode'];
const S = load('u500-loan', {});
const num = (id) => Number($(id).value) || 0;
const fmt = (n) => Math.round(n).toLocaleString();

function render() {
  const P = num('l-amt');
  const r = num('l-rate') / 1200;
  const Y = num('l-course');
  const T = num('l-term');
  const payDuring = $('l-mode').value === '1';
  const studyInterest = P * (num('l-rate') / 100) * Y;
  const balance = payDuring ? P : P + studyInterest;
  const n = Math.max(1, Math.round(T * 12));
  const emi = r === 0 ? balance / n : (balance * r * Math.pow(1 + r, n)) / (Math.pow(1 + r, n) - 1);
  const repaid = emi * n;
  const totalInterest = repaid - balance + studyInterest;
  const totalPaid = repaid + (payDuring ? studyInterest : 0);

  const box = $('l-out');
  box.textContent = '';
  const line = (label, value, cls = 'line') => {
    const row = document.createElement('div');
    row.className = cls;
    const k = document.createElement('span');
    k.textContent = label;
    const b = document.createElement('b');
    b.textContent = value;
    row.append(k, b);
    box.appendChild(row);
  };
  line('Monthly instalment', fmt(emi), 'line big');
  line('Interest during study', fmt(studyInterest) + (payDuring ? ', paid as you go' : ', added to the loan'));
  line('Balance when repayment starts', fmt(balance));
  line('Total interest', fmt(totalInterest));
  line('Total you repay', fmt(totalPaid));
  line('Instalments', n + ' months');
  const note = document.createElement('p');
  note.className = 'src';
  note.textContent = 'You repay ' + (P ? Math.round((100 * totalPaid) / P) : 0) + '% of what you borrow over the full term.';
  box.appendChild(note);
}

IDS.forEach((id) => {
  if (S[id] !== undefined && S[id] !== '') $(id).value = S[id];
  ['input', 'change'].forEach((ev) =>
    $(id).addEventListener(ev, () => {
      S[id] = $(id).value;
      save('u500-loan', S);
      render();
    }),
  );
});
render();
