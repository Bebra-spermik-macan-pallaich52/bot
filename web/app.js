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
function renderForecast(component) {
  const report=component?.report, forecast=report?.forecast;
  $('forecast-values').hidden=true;
  $('forecast-folds').replaceChildren();
  text('forecast-time','От закрытия последней доступной свечи, не траектория внутри периода.');
  const reasons={training_history_too_short:'Нужно не менее 30 дней истории для обучения.',insufficient_contiguous_samples:'Недостаточно непрерывных обучающих данных.',insufficient_class_samples:'Слишком мало примеров одного из направлений.',no_candles:'Свечей пока нет.',stale_candles:'Свечи устарели — новый прогноз не публикуется.',gaps_or_invalid_features:'Есть пропуски или некорректные данные в недавнем окне.',incompatible_model:'Модель не соответствует текущему окну.',old_forecast_report:'Расчёт прогноза давно не обновлялся.',expired_forecast:'Срок прогноза истёк.',calculation_failed:'Ошибка расчёта. Подробности — в логах forecaster.',different_config:'Ожидаем прогноз для текущих настроек.',database_unavailable:'База данных недоступна. Актуальность прогноза не подтверждена.'};
  const evidence=report?.validation?.evidence;
  const conclusion=evidence==='exploratory_edge' ? 'На исторических периодах есть предварительное преимущество над базой. Нужна проверка на новых прогнозах.' : evidence==='no_edge_detected' ? 'На исторической проверке надёжное преимущество над базой не обнаружено.' : 'Исторических проверочных периодов пока недостаточно для оценки преимущества.';
  badge('forecast-badge',forecast && component.state==='ok' ? 'Экспериментальный прогноз':'Нет актуального прогноза', 'warn');
  const names={down:'падение',flat:'небольшое изменение',up:'рост'};
  text('forecast-message',forecast && component.state==='ok' ? `Наибольшая вероятность: ${names[forecast.most_likely] || '—'}. ${conclusion}` : reasons[component?.reason] || 'Ожидаем модель и свежие данные.');
  if(forecast && component.state==='ok') {
    $('forecast-values').hidden=false;
    text('forecast-time',`Снимок: ${date(forecast.asof_ms)} UTC · цена к ${date(forecast.target_ms)} UTC`);
    const band=report.band_bps/100;
    text('down-label',`Падение ниже −${band.toFixed(2)}%`);
    text('flat-label',`Изменение в пределах ±${band.toFixed(2)}%`);
    text('up-label',`Рост выше +${band.toFixed(2)}%`);
    for(const cls of ['down','flat','up']) text(`prob-${cls}`,`${(forecast.probabilities[cls]*100).toFixed(1)}%`);
    text('forecast-reference',number(forecast.reference_price)); text('forecast-price',number(forecast.estimated_price));
    text('forecast-range',`${number(forecast.interval80_price[0])} – ${number(forecast.interval80_price[1])}`);
    text('forecast-return',`Оценка среднего изменения: ${pct(forecast.expected_return_pct)}. Вероятности относятся к цене в конце десяти минут; промежуточный ход неизвестен.`);
  }
  const validation=report?.validation, summary=validation?.summary;
  const ratio=v=>Number.isFinite(v) ? `${(v*100).toFixed(1)}%`:'—';
  text('forecast-validation',summary ? `${validation.evaluated_folds} периодов · ${number(summary.observations)} неперекрывающихся исходов. Log loss: ${summary.log_loss.toFixed(4)} против ${summary.baseline_log_loss.toFixed(4)} у базы (меньше лучше). ${conclusion}`:'Обучение 30 дней (последние 5 — калибровка), затем проверка на следующих 10 днях. Для нескольких полных периодов нужна более длинная история.');
  if(!validation?.folds?.length) empty($('forecast-folds'),'Полных проверочных периодов пока нет.',5);
  else for(const fold of validation.folds) {
    const m=fold.metrics;
    row($('forecast-folds'),[`${date(fold.test_start_ms)} – ${date(fold.test_end_ms)}`,m ? number(m.observations):'Пропущен',m ? `${ratio(m.accuracy)} / ${ratio(m.baseline_accuracy)}`:'Мало данных',m ? `${m.log_loss.toFixed(4)} / ${m.baseline_log_loss.toFixed(4)}`:'—',m ? ratio(m.interval80_coverage):'—']);
  }
  const live=report?.prospective;
  text('forecast-prospective',live ? `Проверка новых прогнозов: записано ${number(live.issued_predictions)}, оценено ${number(live.observations)} на сетке 10 минут. ${live.metrics ? `Log loss: ${live.metrics.log_loss.toFixed(4)} / база ${live.metrics.baseline_log_loss.toFixed(4)}.`:'Ожидаем завершённых исходов.'} Прогнозы сохраняются до появления исхода и не перезаписываются.`:'Журнал новых прогнозов начнёт накапливаться после обучения модели.');
}
function render(data) {
  text('instrument',`${data.symbol} · ${data.category} · 1 мин`);
  text('updated',`Проверено: ${date(data.generated_at_ms)} UTC`);
  renderForecast(data.forecast);
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
