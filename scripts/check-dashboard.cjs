// Optional browser regression check against a running local dashboard.
// Requires Playwright + a Chromium browser; never modifies PostgreSQL.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const base=process.env.CPL_DASHBOARD_URL || 'http://127.0.0.1:8080';
(async()=>{
 const browser=await chromium.launch({...(process.env.CHROMIUM_PATH ? {executablePath:process.env.CHROMIUM_PATH} : {}),headless:true,args:['--no-sandbox','--disable-dev-shm-usage']});
 const errors=[];
 const context=await browser.newContext({viewport:{width:1440,height:1000}});
 const page=await context.newPage();
 page.on('pageerror',e=>errors.push(e.message));
 await page.goto(base);
 await page.waitForFunction(()=>document.querySelector('#db-state').textContent==='Доступна');
 if(await page.locator('#daily .day').count()<1) throw new Error('No coverage bars');
 const fixture=await (await page.request.get(`${base}/api/status`)).json();
 const stamp=Date.now();
 const forecastMetric={observations:400,accuracy:.55,baseline_accuracy:.58,log_loss:1.0,baseline_log_loss:.95,interval80_coverage:.82};
 fixture.forecast={state:'ok',report:{status:'experimental',band_bps:10,
   forecast:{asof_ms:stamp-1000,target_ms:stamp+599000,reference_price:100000,estimated_price:100010,
     probabilities:{down:.2,flat:.55,up:.25},most_likely:'flat',interval80_price:[99800,100200],expected_return_pct:.01},
   validation:{evidence:'no_edge_detected',evaluated_folds:3,
     summary:{observations:1200,log_loss:1.0,baseline_log_loss:.95},
     folds:[0,1,2].map(i=>({test_start_ms:stamp-(30-i*10)*86400000,test_end_ms:stamp-(20-i*10)*86400000,metrics:forecastMetric}))},
   prospective:{issued_predictions:20,observations:2,metrics:null}}};
 const metric={observations:71,sufficient_sample:true,directional_mean_pct:-0.0364,
               cost_sensitivity_mean_pct:-0.1364,mean_ci95_day_bootstrap_pct:[-0.07,0.01]};
 fixture.analyst={state:'ok',generated_at_ms:Date.now(),report:{status:'evaluated',rows:43210,
    split_ms:Date.now()-86400000,fixed_split:false,patterns:['up','down'].map(direction=>({
      direction,volume_threshold:2,test:{'15m':metric,'60m':metric}}))}};
 await page.route('**/api/status',route=>route.fulfill({json:fixture}));
 await page.getByRole('button',{name:'Обновить',exact:true}).click();
 await page.waitForFunction(()=>document.querySelectorAll('#patterns tr').length===4);
 if(!(await page.locator('#research-note').innerText()).includes('автоматическое 70/30')) throw new Error('Missing split warning');
 if(!(await page.locator('#patterns').innerText()).includes('-0.0364%')) throw new Error('Incorrect report formatting');
 if(!await page.locator('#forecast-values').isVisible()) throw new Error('Forecast probabilities hidden');
 if(await page.locator('#prob-up').innerText()!=='25.0%') throw new Error('Incorrect 10m probability');
 if(!(await page.locator('#forecast-message').innerText()).includes('не обнаружено')) throw new Error('Missing no-edge warning');
 if(await page.locator('#forecast-folds tr').count()!==3) throw new Error('Missing walk-forward rows');

 const expired=JSON.parse(JSON.stringify(fixture));
 expired.forecast={state:'expired',reason:'expired_forecast',report:{...fixture.forecast.report,forecast:null}};
 await page.unroute('**/api/status');
 await page.route('**/api/status',r=>r.fulfill({json:expired}));
 await page.getByRole('button',{name:'Обновить',exact:true}).click();
 await page.waitForFunction(()=>document.querySelector('#forecast-values').hidden);
 if(!(await page.locator('#forecast-message').innerText()).includes('истёк')) throw new Error('Expired forecast shown');
 const degraded=JSON.parse(JSON.stringify(fixture));
 degraded.database={state:'unavailable',reason:'query_failed'}; degraded.quality=null;
 degraded.forecast={state:'unknown',reason:'database_unavailable',report:{...fixture.forecast.report,forecast:null}};
 degraded.backfill.state='error';degraded.backfill.last_error_kind='http_403';
 degraded.analyst={state:'stale',report:null};
 await page.unroute('**/api/status');
 await page.route('**/api/status',r=>r.fulfill({json:degraded}));
 await page.getByRole('button',{name:'Обновить',exact:true}).click();
 await page.waitForFunction(()=>document.querySelector('#db-state').textContent==='Нет связи');
 if(await page.locator('#total').innerText()!=='—') throw new Error('Stale totals retained');
 if(!(await page.locator('#patterns').innerText()).includes('Свежего отчёта')) throw new Error('Stale analysis retained');
 await page.unroute('**/api/status');
 await page.route('**/api/status',r=>r.abort());
 await page.getByRole('button',{name:'Обновить',exact:true}).click();
 await page.waitForFunction(()=>!document.querySelector('#connection-error').hidden);
 if(!await page.locator('body').evaluate(el=>el.classList.contains('offline'))) throw new Error('No offline status');
 await page.unroute('**/api/status');
 await page.route('**/api/status',r=>r.fulfill({json:fixture}));
 await page.getByRole('button',{name:'Обновить',exact:true}).click();
 await page.waitForFunction(()=>document.querySelector('#connection-error').hidden);
 await page.setViewportSize({width:390,height:844});
 if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)) throw new Error('Mobile document overflow');
 if(errors.length) throw new Error(errors.join('\n'));
 console.log('Browser checks passed: actual API, report, DB failure, network loss, recovery, 10m forecast, no-edge warning, expired forecast, 390px mobile, no page errors.');
 await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
