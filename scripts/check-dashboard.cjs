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
 const degraded=JSON.parse(JSON.stringify(fixture));
 degraded.database={state:'unavailable',reason:'query_failed'}; degraded.quality=null;
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
 console.log('Browser checks passed: actual API, report, DB failure, network loss, recovery, 390px mobile, no page errors.');
 await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
