import path from 'path'; import { fileURLToPath } from 'url'; import puppeteer from 'puppeteer-core'; import assert from 'assert';
const __dirname=path.dirname(fileURLToPath(import.meta.url)); const root=path.resolve(__dirname,'..');
const browser=await puppeteer.launch({executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true,args:['--no-sandbox','--allow-file-access-from-files','--enable-webgl','--ignore-gpu-blocklist','--enable-unsafe-swiftshader','--use-angle=metal','--hide-scrollbars','--force-color-profile=srgb']});
let failures=0;
function check(cond,msg){ if(cond) console.log('PASS',msg); else {failures++; console.log('FAIL',msg);} }
const page=await browser.newPage(); await page.setViewport({width:1440,height:900,deviceScaleFactor:1});
const errors=[]; page.on('pageerror',e=>errors.push(e.message)); page.on('console',m=>{if(m.type()==='error')errors.push(m.text())});
await page.goto('file://'+path.join(root,'7-eleven-store-3d.html')+'?intro=0&auto=0&mode=night',{waitUntil:'load',timeout:120000});
await page.waitForFunction('window.__SEVEN_READY__ === true',{timeout:120000});
await new Promise(r=>setTimeout(r,1200));
const initial=await page.evaluate(()=>({mode:document.body.dataset.mode,active:document.querySelector('.mode-btn.is-active')?.dataset.mode,ready:window.__SEVEN__.ready,stats:window.__SEVEN__.stats(),loading:getComputedStyle(document.getElementById('loading')).visibility}));
console.log('initial',initial);
check(initial.mode==='night','default mode is night');
check(initial.active==='night','night mode button active');
check(initial.ready,'viewer ready');
check(initial.loading==='hidden','loading overlay hidden');
// Layout
const layout=await page.evaluate(()=>{
 const ids=['masthead','mode-bar','caption','view-tools','hint','micro-footer'];
 const out={}; for(const s of ['.masthead','.mode-bar','.time-row','.caption','.view-tools','.hint','.micro-footer']){const e=document.querySelector(s); const r=e.getBoundingClientRect(); out[s]={left:r.left,top:r.top,right:r.right,bottom:r.bottom,w:r.width,h:r.height,display:getComputedStyle(e).display,opacity:getComputedStyle(e).opacity};}
 return {out, sw:document.documentElement.scrollWidth, iw:innerWidth, sh:document.documentElement.scrollHeight, ih:innerHeight};
});
console.log('layout',JSON.stringify(layout));
for (const [sel,r] of Object.entries(layout.out)) {
 if(r.display==='none') continue;
 check(r.left>=-1 && r.top>=-1 && r.right<=layout.iw+1 && r.bottom<=layout.ih+1, `${sel} inside viewport`);
}
check(layout.sw<=layout.iw+1,'no horizontal overflow');
// Time-of-day slider: dusk is a real intermediate state.
await page.evaluate(() => window.__SEVEN__.setHour(17.5));
await new Promise(r=>setTimeout(r,1100));
const dusk=await page.evaluate(()=>({mode:document.body.dataset.mode,caption:document.getElementById('caption-title').textContent,value:document.getElementById('time-range').value,readout:document.getElementById('time-now').textContent,active:document.querySelectorAll('.mode-btn.is-active').length}));
console.log('dusk',dusk);
check(dusk.mode==='dusk','time slider reaches dusk');
check(dusk.caption.includes('暗'),'dusk caption');
check(dusk.active===0,'no day/night button active at dusk');
check(/^\d{2}:\d{2}$/.test(dusk.readout),'time readout visible');
await page.screenshot({path:path.join(root,'renders','_test-dusk.png')});
await page.click('.mode-btn[data-mode="night"]');
await new Promise(r=>setTimeout(r,900));

// Switch to day, assert values and caption.
await page.click('.mode-btn[data-mode="day"]');
await new Promise(r=>setTimeout(r,1400));
const day=await page.evaluate(()=>({mode:document.body.dataset.mode,active:document.querySelector('.mode-btn.is-active')?.dataset.mode,pressed:document.querySelector('.mode-btn[data-mode="day"]').getAttribute('aria-pressed'),caption:document.getElementById('caption-title').textContent,exposure:window.__SEVEN__.renderer.toneMappingExposure}));
console.log('day',day);
check(day.mode==='day'&&day.active==='day','day mode activated');
check(day.pressed==='true','day aria state updated');
check(day.caption.includes('醒'),'day mode + caption');
await page.screenshot({path:path.join(root,'renders','_test-day.png')});
// Auto rotate toggle
// Auto rotate toggle
await page.click('#btn-rotate');
const auto=await page.evaluate(()=>({active:document.getElementById('btn-rotate').classList.contains('is-on'),orbit:window.__SEVEN__.orbit.autoRotate}));
console.log('auto',auto);
check(auto.active,'auto rotate UI on');
// reset
await page.evaluate(()=>window.__SEVEN__.camera.position.set(0,20,40));
await page.click('#btn-reset'); await new Promise(r=>setTimeout(r,1300));
const reset=await page.evaluate(()=>window.__SEVEN__.camera.position.toArray().map(v=>+v.toFixed(2)));
console.log('reset',reset);
check(reset[1]<10 && reset[2]>10,'camera reset to default');
// modal
await page.click('#btn-info'); await new Promise(r=>setTimeout(r,500));
let modal=await page.evaluate(()=>({open:document.getElementById('info-modal').classList.contains('is-open'),aria:document.getElementById('info-modal').getAttribute('aria-hidden'),visible:getComputedStyle(document.getElementById('info-modal')).visibility}));
console.log('modal',modal); check(modal.open&&modal.aria==='false'&&modal.visible==='visible','info modal opens');
await page.screenshot({path:path.join(root,'renders','_test-modal.png')});
await page.keyboard.press('Escape'); await new Promise(r=>setTimeout(r,500));
modal=await page.evaluate(()=>({open:document.getElementById('info-modal').classList.contains('is-open'),aria:document.getElementById('info-modal').getAttribute('aria-hidden')}));
console.log('modal closed',modal); check(!modal.open&&modal.aria==='true','info modal closes with Escape');
// Photo mode.
await page.click('#btn-photo'); await new Promise(r=>setTimeout(r,350));
const photo=await page.evaluate(()=>({photo:document.body.classList.contains('photo-mode'),bar:getComputedStyle(document.getElementById('photo-bar')).display}));
console.log('photo',photo);
check(photo.photo,'photo mode enters');
check(photo.bar==='flex','photo bar visible');
await page.keyboard.press('Escape'); await new Promise(r=>setTimeout(r,350));
check(!(await page.evaluate(()=>document.body.classList.contains('photo-mode'))),'photo mode exits');

// Enter the store with the view-tool button, then leave with Escape.
await page.click('#btn-enter'); await new Promise(r=>setTimeout(r,2700));
const interior=await page.evaluate(()=>({
  inside: document.body.classList.contains('inside'),
  pos: window.__SEVEN__.camera.position.toArray().map(v=>+v.toFixed(2)),
  doorL: window.__SEVEN__.scene.getObjectByName('Door_Leaf_Left')?.position.x,
}));
console.log('interior',interior);
check(interior.inside,'guided entry reaches interior');
check(interior.pos[2] < 4.8,'interior camera is inside the storefront');
check(interior.doorL < -0.4,'sliding door opened');
await page.screenshot({path:path.join(root,'renders','_test-interior.png')});

// Night coffee: order a specific drink, pay with UnionPay, then inspect artifacts.
await page.click('#btn-coffee'); await new Promise(r=>setTimeout(r,350));
check(await page.evaluate(()=>document.getElementById('coffee-modal').classList.contains('is-open')),'coffee order opens');
await page.click('[data-coffee="mocha"]'); await page.click('[data-temp="iced"]');
await page.click('#coffee-next'); await new Promise(r=>setTimeout(r,250));
await page.click('[data-pay="unionpay"]');
const coffeePay=await page.evaluate(()=>({
  stage: document.querySelector('.coffee-stage.is-active')?.dataset.coffeeStage,
  name: document.getElementById('coffee-preview-name').textContent,
  method: document.querySelector('.coffee-pay-method.is-selected')?.dataset.pay,
  disabled: document.getElementById('coffee-pay').disabled,
  qr: document.getElementById('coffee-qr').naturalWidth,
}));
console.log('coffee pay',coffeePay);
check(coffeePay.name==='冰摩卡','coffee variety and temperature selected');
check(coffeePay.method==='unionpay','UnionPay selected');
check(coffeePay.disabled===false&&coffeePay.qr===320,'simulated QR ready');
await page.click('#coffee-discount');
const coffeeDiscount=await page.evaluate(()=>({total:document.getElementById('coffee-pay-total').textContent,line:document.getElementById('coffee-discount-line').hidden,discount:document.getElementById('coffee-discount-value').textContent}));
console.log('coffee discount',coffeeDiscount);
check(coffeeDiscount.total==='¥16','coffee X user discount total');
check(coffeeDiscount.line===false,'coffee discount line visible');
await page.click('#coffee-pay'); await new Promise(r=>setTimeout(r,1550));
const coffeeDone=await page.evaluate(()=>({
  stage: document.querySelector('.coffee-stage.is-active')?.dataset.coffeeStage,
  receipt: document.getElementById('coffee-receipt-img').naturalWidth,
  card: document.getElementById('coffee-card-img').naturalWidth,
}));
console.log('coffee done',coffeeDone);
check(coffeeDone.stage==='success','simulated payment reaches success');
check(coffeeDone.receipt===720&&coffeeDone.card===1080,'receipt and coffee card generated');
await page.screenshot({path:path.join(root,'renders','_test-coffee.png')});
await page.keyboard.press('Escape'); await new Promise(r=>setTimeout(r,450));
check(!(await page.evaluate(()=>document.getElementById('coffee-modal').classList.contains('is-open'))),'coffee modal closes with Escape');
check(await page.evaluate(()=>document.body.classList.contains('inside')),'coffee close stays inside');

// Rail walk to the snack shelf, then shop with the bag.
await page.click('[data-route-stop="snacks"]');
await new Promise(r=>setTimeout(r,2200));
const rail=await page.evaluate(()=>({
  pos: window.__SEVEN__.camera.position.toArray().map(v=>+v.toFixed(2)),
  shop: document.getElementById('shop-modal').classList.contains('is-open'),
  category: document.querySelector('.shop-tabs .is-active')?.dataset.shopCat,
  current: document.querySelector('.route-bar .is-current')?.dataset.routeStop,
}));
console.log('rail shop',rail);
check(rail.shop,'shelf walk opens the shop panel');
check(rail.category==='snacks','shelf category follows the rail stop');
check(rail.current==='snacks','route bar tracks the stop');
await page.click('[data-shop-add="chips"]');
await page.click('[data-shop-cat="daily"]'); await new Promise(r=>setTimeout(r,120));
await page.click('[data-shop-add="condom"]');
const bag=await page.evaluate(()=>({count:document.getElementById('shop-cart-count').textContent,total:document.getElementById('shop-total').textContent,badge:document.getElementById('bag-count').textContent}));
console.log('bag',bag);
check(bag.badge!=='0','bag badge updates');
await page.click('#shop-checkout'); await new Promise(r=>setTimeout(r,250));
await page.click('[data-shop-pay="alipay"]');
check(await page.evaluate(()=>!document.getElementById('shop-pay').disabled),'shop payment method enables pay');
await page.click('#shop-discount');
const shopDiscount=await page.evaluate(()=>({total:document.getElementById('shop-pay-total').textContent,line:document.getElementById('shop-discount-line').hidden,discount:document.getElementById('shop-discount-value').textContent}));
console.log('shop discount',shopDiscount);
check(shopDiscount.total!=='¥25','shop X user discount applied');
check(shopDiscount.line===false,'shop discount line visible');
await page.click('#shop-pay'); await new Promise(r=>setTimeout(r,1600));
const shopDone=await page.evaluate(()=>({
  stage: document.querySelector('.shop-stage.is-active')?.dataset.shopStage,
  receipt: document.getElementById('shop-receipt-img').naturalWidth,
  bag: document.getElementById('bag-count').textContent,
}));
console.log('shop done',shopDone);
check(shopDone.stage==='success','shop payment reaches success');
check(shopDone.receipt===720,'shopping receipt generated');
check(shopDone.bag==='0','bag clears after payment');
await page.screenshot({path:path.join(root,'renders','_test-shop.png')});
await page.keyboard.press('Escape'); await new Promise(r=>setTimeout(r,500));
check(await page.evaluate(()=>document.getElementById('shop-modal').classList.contains('is-open')===false),'shop modal closes');
check(await page.evaluate(()=>getComputedStyle(document.getElementById('route-bar')).display==='flex'),'route bar returns after shop');
await page.keyboard.press('Escape'); await new Promise(r=>setTimeout(r,900));
check(!(await page.evaluate(()=>document.body.classList.contains('inside'))),'exit returns to street');

// switch back to night, UI screenshot
await page.click('.mode-btn[data-mode="night"]'); await new Promise(r=>setTimeout(r,1700));
await page.screenshot({path:path.join(root,'renders','_test-viewer.png')});
check(errors.length===0,'no page errors'); console.log('errors',errors);
await page.close();
// mobile layout
const mobile=await browser.newPage(); await mobile.setViewport({width:390,height:844,deviceScaleFactor:2,isMobile:true,hasTouch:true});
const merrors=[]; mobile.on('pageerror',e=>merrors.push(e.message)); mobile.on('console',m=>{if(m.type()==='error')merrors.push(m.text())});
await mobile.goto('file://'+path.join(root,'7-eleven-store-3d.html')+'?intro=0&auto=0&mode=night',{waitUntil:'load',timeout:120000});
await mobile.waitForFunction('window.__SEVEN_READY__ === true',{timeout:120000});
await new Promise(r=>setTimeout(r,1500));
const ml=await mobile.evaluate(()=>{
 const sels=['.masthead','.mode-bar','.time-row','.view-tools','.route-bar','.store-services'];
 const out={}; for(const s of sels){const r=document.querySelector(s).getBoundingClientRect(); out[s]={left:r.left,top:r.top,right:r.right,bottom:r.bottom,w:r.width,h:r.height,display:getComputedStyle(document.querySelector(s)).display};}
 return {out,sw:document.documentElement.scrollWidth,iw:innerWidth,sh:document.documentElement.scrollHeight,ih:innerHeight,mode:document.body.dataset.mode};
});
console.log('mobile layout',JSON.stringify(ml));
for(const [s,r] of Object.entries(ml.out)){if(r.display==='none')continue; check(r.left>=-1&&r.right<=ml.iw+1&&r.top>=-1&&r.bottom<=ml.ih+1,`mobile ${s} inside viewport`);}
check(ml.sw<=ml.iw+1,'mobile no horizontal overflow');
await mobile.screenshot({path:path.join(root,'renders','_test-mobile.png')});
check(merrors.length===0,'mobile no page errors'); console.log('mobile errors',merrors);
await mobile.close();
await browser.close();
console.log(failures===0?'ALL PASS':`${failures} FAILURES`);
process.exit(failures===0?0:1);
