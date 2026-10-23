'use strict';
const $ = id => document.getElementById(id);
const number = v => Number.isFinite(v) ? new Intl.NumberFormat('ru-RU').format(v) : '—';
const pct = v => Number.isFinite(v) ? `${v.toFixed(4)}%` : '—';
const date = v => Number.isFinite(v) ? new Intl.DateTimeFormat('ru-RU', {timeZone:'UTC',dateStyle:'short',timeStyle:'short'}).format(new Date(v)) : '—';
function text(id, value) { $(id).textContent = value; }
function badge(id, label, tone='warn') { text(id,label); $(id).className = `badge ${tone}`; }
function state(id,label,tone) { text(id,label); $(id).className=tone; }
function row(body, values) { const tr=document.createElement('tr'); for(const value of values) { const td=document.createElement('td'); td.textContent=value; tr.append(td); } body.append(tr); }
function empty(body, message, columns) { body.replaceChildren(); const tr=document.createElement('tr'); const td=document.createElement('td'); td.colSpan=columns; td.textContent=message; tr.append(td); body.append(tr); }
function render(data) {
  text('instrument',`${data.symbol} · ${data.category} · 1 мин`);
  text('updated',`Проверено: ${date(data.generated_at_ms)} UTC`);
  const q=data.quality;
  state('db-state',data.database.state==='ok' ? 'Доступна' : 'Нет связи',data.database.state==='ok' ? 'ok':'bad');
  text('db-note',data.database.state==='ok' ? 'Запрос качества выполнен' : 'Не удалось получить данные из БД');
  state('live-state',q?.fresh ? 'Свежие данные' : q?.present_candles ? 'Есть задержка / пропуски' : 'Нет подтверждения',q?.fresh ? 'ok':'bad');
  text('live-note',q ? `Последние минуты: ${q.recent_present}/${q.recent_expected} · задержка закрытия ${number(q.latest_close_age_seconds === null ? null : Math.round(q.latest_close_age_seconds))} с` : 'Состояние потока неизвестно');
  const rest=data.backfill;
  const restLabels={ok:'Восстановление работает',error:'Ошибка дозагрузки',pending:'Выполняется',stale:'Нет свежего успеха',unknown:'Нет подтверждения'};
  state('rest-state',restLabels[rest.state]||'Неизвестно',rest.state==='ok' ? 'ok':rest.state==='error' ? 'bad':'warn');
  const errors={http_403:'Bybit REST вернул HTTP 403: проверьте доступ и регион сервера.',http_429:'Bybit ограничил частоту запросов.',http_error:'Ошибка HTTP при дозагрузке.',network:'Сетевая ошибка при дозагрузке.',database:'Ошибка записи дозагрузки в БД.',invalid_response:'Получен некорректный ответ REST.',internal:'Ошибка дозагрузчика.'};
  text('rest-note',errors[rest.last_error_kind] || (rest.reason==='different_config' ? 'Нет результата для текущего инструмента и окна.' : `Полное окно: ${date(rest.last_full_success_ms)} UTC · недавние свечи: ${date(rest.last_recent_success_ms)} UTC`));
  const analyst=data.analyst;
  state('analyst-state',analyst.state==='ok' ? 'Отчёт обновляется' : analyst.state==='stale' ? 'Отчёт устарел':'Нет свежего отчёта',analyst.state==='ok' ? 'ok':'warn');
  text('analyst-note',analyst.generated_at_ms ? `Отчёт: ${date(analyst.generated_at_ms)} UTC`:'Ожидаем отчёт текущего инструмента');
  for(const [id,val] of [['total',q?.total_candles],['missing',q?.missing_candles],['invalid',q?.invalid_candles]]) text(id,number(val));
  text('coverage',q ? `${q.coverage_pct.toFixed(2)}%`:'—');
  text('last-candle',q ? `${date(q.latest_closed_start_ms)} UTC (начало минуты)`:'—');
  text('last-write',q ? `${date(q.last_write_ms)} UTC`:'—');
  text('window-note',q ? `Окно: ${q.window_days} сут. · ${date(q.window_start_ms)} — ${date(q.window_end_ms)} UTC`:'База недоступна — полнота истории неизвестна');
  badge('quality-badge',q?.ready ? 'Данные проверены':q ? 'Требуется внимание':'Нет данных',q?.ready ? 'ok':'warn');
  text('quality-note',q ? `В окне ${number(q.present_candles)} из ${number(q.expected_candles)} минут. Пропусков старше двух минут: ${number(q.settled_missing_candles)}; ожидают доставки: ${number(q.pending_recent_candles)}. Незакрытых / будущих свечей в БД: ${number(q.unclosed_or_future_candles)}; свечей вне минутной сетки: ${number(q.off_grid_candles_total)}.` : 'Не удалось проверить историю. Ранее полученные цифры не используются как текущие.');
  $('daily').replaceChildren();
  for(const d of q?.daily || []) { const bar=document.createElement('button'); bar.type='button'; bar.className=`day${d.missing ? ' gap':''}`; const label=`${date(d.day_ms).split(',')[0]} UTC: ${d.present}/${d.expected} минут, пропущено ${d.missing}`; bar.title=label; bar.setAttribute('aria-label',label); bar.style.height=`${Math.max(6,Math.round(80*d.present/d.expected))}px`; $('daily').append(bar); }
  const gaps=$('gaps'); gaps.replaceChildren();
  if(!q) empty(gaps,'Нет актуальной проверки',3);
  else if(!q.gap_ranges.length) empty(gaps,'Пропусков в проверенном окне нет',3);
  else for(const g of q.gap_ranges) row(gaps,[date(g.start_ms),date(g.end_ms),number(g.minutes)]);
  text('gap-note',q ? `Диапазонов: ${number(q.gap_ranges_total)}${q.ranges_truncated ? `. Показаны первые ${q.gap_ranges.length}; итоговые счётчики учитывают все.`:'.'}`:'Проверка недоступна');
  const report=analyst.report, patterns=$('patterns'); patterns.replaceChildren();
  if(!report || report.status!=='evaluated') { empty(patterns,report?.status==='insufficient_history' ? `Недостаточно истории: ${number(report.rows)} свечей.`:'Свежего отчёта для текущего инструмента нет.',6); badge('research-badge','Ожидание данных'); text('research-note','Численные результаты пока недоступны.'); return; }
  badge('research-badge','Исследовательские результаты','warn');
  text('research-note',`${number(report.rows)} свечей · граница test: ${date(report.split_ms)} UTC · ${report.fixed_split ? 'фиксированная граница':'автоматическое 70/30, разведочный режим'}`);
  for(const p of report.patterns || []) {
    const name=p.direction==='up' ? 'Пробой вверх':'Пробой вниз';
    if(!p.test) { row(patterns,[name,'—','Мало событий на train','—','—','—']); continue; }
    for(const h of ['15m','60m']) { const m=p.test[h]; if(!m) continue; const ci=m.mean_ci95_day_bootstrap_pct; row(patterns,[`${name} · объём ≥${p.volume_threshold}×`,h==='15m'?'15 мин':'60 мин',`${number(m.observations)}${m.sufficient_sample ? '':' · мало данных'}`,pct(m.directional_mean_pct),Array.isArray(ci) ? `${pct(ci[0])} … ${pct(ci[1])}`:'Недостаточно дней',pct(m.cost_sensitivity_mean_pct)]); }
  }
}
let loading=false;
async function refresh() {
  if(loading) return;
  loading=true; $('refresh').disabled=true;
  try { const response=await fetch('/api/status',{cache:'no-store',signal:AbortSignal.timeout(25000)}); if(!response.ok) throw new Error('status'); const data=await response.json(); render(data); $('connection-error').hidden=true; document.body.classList.remove('offline'); }
  catch (_) { $('connection-error').hidden=false; document.body.classList.add('offline'); text('updated','Нет актуального соединения'); }
  finally { loading=false; $('refresh').disabled=false; }
}
$('refresh').addEventListener('click',refresh);
refresh(); setInterval(refresh,15000);
