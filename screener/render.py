"""Renders the dashboard: one self-contained, interactive HTML file."""
from __future__ import annotations

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CSS = """
:root{
  --bg:#FFFFFF; --panel:#F2F5FC; --line:#DCE3F2;
  --ink:#080B14; --muted:#5A6480;
  --blue:#1B4DFF; --blue-soft:#E4EAFF;
  --green:#00A24A; --green-soft:#DBF7E7;
  --red:#E01B1B; --red-soft:#FFE3E3;
  --amber:#E07C00; --amber-soft:#FFF0D6;
}
*{box-sizing:border-box;margin:0;padding:0}
html{-webkit-text-size-adjust:100%}
body{background:var(--bg);color:var(--ink);
  font-family:Manrope,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
  font-size:16px;line-height:1.45;font-variant-numeric:tabular-nums;
  padding-bottom:80px}
.wrap{max-width:1040px;margin:0 auto;padding:0 18px}
button{font-family:inherit;cursor:pointer;border:none;background:none;color:inherit}

/* masthead */
.mast{display:flex;align-items:center;flex-wrap:wrap;padding:24px 0 14px}
.mast h1{font-size:22px;font-weight:800;letter-spacing:-.03em}
.mast .stamp{margin-left:auto;font-size:13px;font-weight:600;color:var(--muted)}

/* regime */
.regime{border-radius:14px;padding:22px 22px 18px;color:#fff;background:var(--blue)}
.regime.warn{background:var(--amber)} .regime.bad{background:var(--red)}
.regime .kicker{font-size:13px;font-weight:800;letter-spacing:.04em;opacity:.85}
.regime .line{font-size:clamp(20px,4.2vw,28px);font-weight:800;line-height:1.2;
  letter-spacing:-.025em;margin-top:6px;max-width:32ch}
.regime .facts{display:flex;flex-wrap:wrap;margin-top:16px;padding-top:14px;
  border-top:1.5px solid rgba(255,255,255,.3)}
.regime .fact{margin-right:32px;margin-bottom:4px}
.regime .fact b{display:block;font-size:20px;font-weight:800}
.regime .fact span{font-size:12px;font-weight:600;opacity:.85}

/* tabs */
.tabs{display:flex;gap:6px;overflow-x:auto;margin:22px 0 0;padding-bottom:4px;
  -webkit-overflow-scrolling:touch}
.tab{white-space:nowrap;font-size:14px;font-weight:700;padding:9px 15px;
  border-radius:999px;background:var(--panel);color:var(--muted);
  transition:background .15s,color .15s}
.tab:hover{background:var(--blue-soft);color:var(--blue)}
.tab[aria-selected=true]{background:var(--ink);color:#fff}
.tab .pill{display:inline-block;margin-left:7px;font-size:12px;font-weight:800;
  padding:1px 7px;border-radius:999px;background:rgba(0,0,0,.09)}
.tab[aria-selected=true] .pill{background:rgba(255,255,255,.22)}
.tab .pill.hot{background:var(--red);color:#fff}

.panel{display:none;margin-top:18px}
.panel.on{display:block}
.lede{font-size:14px;font-weight:600;color:var(--muted);margin-bottom:12px}

/* controls */
.controls{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px}
.controls input{flex:1 1 190px;min-width:0;font-size:15px;font-weight:600;
  padding:10px 13px;border:2px solid var(--line);border-radius:10px;background:var(--bg)}
.controls input:focus{outline:none;border-color:var(--blue)}
.sortbtn{font-size:13px;font-weight:700;padding:9px 13px;border-radius:10px;
  background:var(--panel);color:var(--muted)}
.sortbtn.on{background:var(--blue);color:#fff}

/* rows */
.row{display:flex;align-items:flex-start;width:100%;text-align:left;
  padding:14px 12px;border-radius:12px;transition:background .12s}
.row+.row{margin-top:2px}
.row:hover{background:var(--panel)}
.row .rk{flex:0 0 34px;font-size:14px;font-weight:800;color:var(--muted);padding-top:3px}
.row .bd{flex:1 1 auto;min-width:0;padding-right:12px}
.row .rt{flex:0 0 auto;text-align:right}
.sym{font-size:17px;font-weight:800;letter-spacing:-.02em}
.sub{font-size:13px;font-weight:600;color:var(--muted);margin-top:2px}
.stats{font-size:12.5px;font-weight:700;color:var(--muted);margin-top:5px}
.stats b{color:var(--ink);font-weight:800}
.cat{display:inline-block;margin-top:6px;font-size:12.5px;font-weight:800;
  color:var(--amber);background:var(--amber-soft);padding:3px 9px;border-radius:7px}
.big{font-size:19px;font-weight:800;letter-spacing:-.02em}
.up{color:var(--green)} .down{color:var(--red)}
.tag{display:inline-block;margin-top:6px;font-size:12px;font-weight:800;
  padding:3px 10px;border-radius:999px}
.tag.buy{background:var(--green-soft);color:var(--green)}
.tag.hold{background:var(--blue-soft);color:var(--blue)}
.tag.sell{background:var(--red-soft);color:var(--red)}
.tag.wait{background:var(--panel);color:var(--muted)}
.spine{height:6px;border-radius:99px;background:var(--blue-soft);margin-top:8px;max-width:300px}
.spine i{display:block;height:100%;border-radius:99px;background:var(--blue)}

/* exit cards — loudest thing after the regime */
.exit{display:flex;align-items:center;padding:16px;border-radius:12px;
  background:var(--red-soft);border-left:6px solid var(--red)}
.exit+.exit{margin-top:8px}
.exit .bd{flex:1 1 auto;min-width:0}
.exit .sym{color:var(--red)}
.exit .sub{color:#8A1414;font-weight:700}

/* detail drawer */
.detail{display:none;padding:2px 12px 14px 46px}
.detail.on{display:block}
.grid{display:flex;flex-wrap:wrap}
.kv{margin:0 26px 10px 0}
.kv b{display:block;font-size:16px;font-weight:800}
.kv span{font-size:11.5px;font-weight:700;color:var(--muted)}

/* sectors */
.sect{display:flex;align-items:center;padding:11px 12px;border-radius:10px;font-weight:700}
.sect:hover{background:var(--panel)}
.sect .n{flex:0 0 30px;font-size:14px;font-weight:800;color:var(--muted)}
.sect .nm{flex:1 1 auto;min-width:0;font-size:15px;padding-right:10px}
.sect .bar{flex:0 0 110px;height:9px;border-radius:99px;background:var(--panel);margin-right:12px}
.sect .bar i{display:block;height:100%;border-radius:99px;background:var(--blue)}
.sect .pct{flex:0 0 52px;text-align:right;font-size:14px;font-weight:800}
.sect.out{opacity:.4}
.sect.out .bar i{background:var(--muted)}

.empty{padding:20px 12px;border-radius:12px;background:var(--panel);
  font-size:15px;font-weight:700;color:var(--muted)}
footer{margin-top:40px;padding-top:16px;border-top:2px solid var(--line);
  font-size:12.5px;font-weight:600;color:var(--muted);line-height:1.6}
@media(max-width:560px){
  .row{padding:13px 8px}.row .rk{flex-basis:26px}
  .sect .bar{flex-basis:64px}.detail{padding-left:34px}
}
@media(prefers-reduced-motion:reduce){*{transition:none!important}}
"""

JS = r"""
var F={
  pct:function(x,d){d=d==null?1:d;return x==null||isNaN(x)?'--':(x*100).toFixed(d)+'%';},
  spct:function(x,d){d=d==null?0:d;return x==null||isNaN(x)?'--':((x>=0?'+':'')+(x*100).toFixed(d)+'%');},
  num:function(x,d){d=d==null?0:d;return x==null||isNaN(x)?'--':Number(x).toFixed(d);},
  rs:function(x){return x==null||isNaN(x)?'--':'\u20b9'+Math.round(x).toLocaleString('en-IN');},
  cr:function(x){if(!x)return '--';return x>=1000?'\u20b9'+(x/1000).toFixed(1)+'k cr':'\u20b9'+Math.round(x)+' cr';}
};
function esc(s){return String(s==null?'':s).replace(/[&<>"]/g,function(c){
  return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}
function dirOf(x){return (x||0)>=0?'up':'down';}
function kv(v,l){return '<div class="kv"><b>'+v+'</b><span>'+l+'</span></div>';}

function tabs(){
  var ts=document.querySelectorAll('.tab');
  for(var i=0;i<ts.length;i++){
    ts[i].onclick=function(){
      var all=document.querySelectorAll('.tab');
      for(var j=0;j<all.length;j++){all[j].setAttribute('aria-selected','false');}
      var ps=document.querySelectorAll('.panel');
      for(var k=0;k<ps.length;k++){ps[k].className='panel';}
      this.setAttribute('aria-selected','true');
      document.getElementById(this.getAttribute('data-panel')).className='panel on';
      window.scrollTo(0,0);
    };
  }
}

function drawer(host){
  var rows=host.querySelectorAll('.row[data-i]');
  for(var i=0;i<rows.length;i++){
    rows[i].onclick=function(){
      var d=host.querySelector('.detail[data-i="'+this.getAttribute('data-i')+'"]');
      if(d){d.className=(d.className.indexOf('on')>-1)?'detail':'detail on';}
    };
  }
}

function rowHTML(x,i,o){
  o=o||{};
  var tag=o.tag?'<span class="tag '+o.tag[0]+'">'+o.tag[1]+'</span>':'';
  var spine=(o.spine!=null)?'<div class="spine"><i style="width:'+o.spine+'%"></i></div>':'';
  var cat=x.catalyst?'<div class="cat">'+esc(x.catalyst)+'</div>':'';
  var stats='';
  if(x.weekly_rsi!=null||x.ext20!=null||x.price||x.rs_days!=null){
    var rs=(x.rs_days==null||x.rs_days>900)?'':(' \u00b7 RS high <b>'
      +(x.rs_days===0?'today':x.rs_days+'d ago')+'</b>');
    var qq='';
  if(x.eps_qoq!=null||x.sales_qoq!=null){
    qq='<div class="stats">QoQ earnings <b>'+F.spct(x.eps_qoq)+'</b> \u00b7 sales <b>'
      +F.spct(x.sales_qoq)+'</b>'+(x.quarter?' \u00b7 quarter to '+esc(x.quarter):'')+'</div>';
  }
  var sc='';
    if(x.sector_score!=null||x.earnings_score!=null||x.growth_score!=null||x.emergence_score!=null){
      sc='<div class="stats">Emergence <b>'+F.num(x.emergence_score)+'</b> \u00b7 Sector <b>'
        +F.num(x.sector_score)+'</b> \u00b7 Earnings <b>'+F.num(x.earnings_score)
        +'</b> \u00b7 Growth <b>'+F.num(x.growth_score)+'</b></div>';
    }
    stats='<div class="stats">RSI <b>'+F.num(x.weekly_rsi)+'</b> \u00b7 20-day <b>'+F.spct(x.ext20)+'</b>'
      +rs+(o.weight!=null?' \u00b7 weight <b>'+F.pct(o.weight)+'</b>':'')
      +(x.price?' \u00b7 <b>'+F.rs(x.price)+'</b>':'')+'</div>';
  }
  var ret='';
  if(x.eps_growth!==undefined||x.sales_growth!==undefined){
    ret='<div class="big '+dirOf(x.eps_growth)+'">'+F.spct(x.eps_growth)+'</div>'
       +'<div class="sub">earnings YoY</div>'
       +'<div class="big '+dirOf(x.sales_growth)+'" style="margin-top:6px">'+F.spct(x.sales_growth)+'</div>'
       +'<div class="sub">sales YoY</div>';
  }else if(x.r12m!=null){
    ret='<div class="big '+dirOf(x.r12m)+'">'+F.spct(x.r12m)+'</div><div class="sub">1 year</div>';
  }
  var det='<div class="grid">'
    +kv(F.spct(x.r12m),'1 year')+kv(F.spct(x.r6m),'6 months')+kv(F.spct(x.r3m),'3 months')
    +kv(F.pct(x.ann_vol,0),'volatility')+kv(F.num(x.composite,2),'score')
    +kv(F.cr(x.market_cap_cr),'market cap')
    +kv(x.quality_score!=null?x.quality_score+' of 5':'--','fundamentals')
    +kv(F.num(x.sector_score),'sector score')
    +kv(F.num(x.earnings_score),'earnings score')
    +kv(F.num(x.emergence_score),'emergence score')
    +kv(F.num(x.growth_score),'growth score')
    +(x.eps_accel!=null?kv(F.spct(x.eps_accel),'earnings acceleration'):'')
    +(x.eps_qoq!=null?kv(F.spct(x.eps_qoq),'earnings QoQ'):'')
    +(x.sales_qoq!=null?kv(F.spct(x.sales_qoq),'sales QoQ'):'')
    +(x.stop?kv(F.rs(x.stop),'stop price'):'')
    +(x.blocked?kv(esc(x.blocked),'blocked by'):'')+'</div>';
  return '<button class="row" data-i="'+i+'"><div class="rk">'+(x.rank||'')+'</div><div class="bd">'
    +'<div class="sym">'+esc(x.symbol)+'</div>'
    +'<div class="sub">'+esc(x.sector||'')+(x.name?' \u00b7 '+esc(x.name):'')+'</div>'
    +stats+sc+qq+cat+spine+'</div><div class="rt">'+ret+tag+'</div></button>'
    +'<div class="detail" data-i="'+i+'">'+det+'</div>';
}

function list(host,arr,opts,emptyMsg){
  if(!arr||!arr.length){host.innerHTML='<div class="empty">'+emptyMsg+'</div>';return;}
  var out=[];
  for(var i=0;i<arr.length;i++){
    out.push(rowHTML(arr[i],i,(typeof opts==='function')?opts(arr[i]):opts));
  }
  host.innerHTML=out.join('');
  drawer(host);
}

function candidates(){
  var host=document.getElementById('candList');
  var box=document.getElementById('candSearch');
  var key='rank';
  function render(){
    var q=(box.value||'').toLowerCase();
    var a=[];
    for(var i=0;i<DATA.candidates.length;i++){
      var c=DATA.candidates[i];
      var hay=(c.symbol+' '+(c.sector||'')).toLowerCase();
      if(!q||hay.indexOf(q)>-1){a.push(c);}
    }
    if(key==='ready'){
      a=a.filter(function(x){return x.buyable;});
    }else{
      a=a.slice().sort(function(p,n){
        return key==='rank'?(p.rank-n.rank):((n[key]||0)-(p[key]||0));});
    }
    list(host,a,function(x){
      return {tag:x.held?['hold','In book']:(x.buyable?['buy','Ready']:['wait','Too extended'])};
    },'Nothing matches that search.');
  }
  var bs=document.querySelectorAll('.sortbtn');
  for(var i=0;i<bs.length;i++){
    bs[i].onclick=function(){
      var all=document.querySelectorAll('.sortbtn');
      for(var j=0;j<all.length;j++){all[j].className='sortbtn';}
      this.className='sortbtn on';
      key=this.getAttribute('data-key');render();
    };
  }
  box.oninput=render;render();
}

function boot(){
  tabs();
  list(document.getElementById('exitList'),DATA.exits,{tag:['sell','Sell']},
    'Nothing to sell. Every holding is above its 21-week EMA and inside its stop.');
  var buys=DATA.book.filter(function(x){return x.action==='buy';});
  list(document.getElementById('entryList'),buys,function(x){
    return {tag:['buy','Buy'],weight:x.weight};},
    'Nothing to buy today. The next scheduled rebalance is '+DATA.next_rebalance+'.');
  list(document.getElementById('signalList'),DATA.new_signals,{tag:['buy','New']},
    'Nothing new cleared the entry rules since the last run.');
  var top=1;
  for(var i=0;i<DATA.book.length;i++){top=Math.max(top,Math.abs(DATA.book[i].composite||0));}
  list(document.getElementById('bookList'),DATA.book,function(x){
    return {tag:[x.action,x.action==='buy'?'Buy':'Hold'],weight:x.weight,
            spine:Math.min(100,Math.max(5,(x.composite/top)*100))};},
    'No positions yet. Run a rebalance.');
  var sh=[];
  for(var s=0;s<DATA.sectors.length;s++){
    var sec=DATA.sectors[s];
    sh.push('<div class="sect'+(sec.rank<=DATA.top_sectors?'':' out')+'">'
      +'<span class="n">'+sec.rank+'</span><span class="nm">'+esc(sec.sector)+'</span>'
      +'<span class="bar"><i style="width:'+Math.max(3,sec.breadth*100).toFixed(0)+'%"></i></span>'
      +'<span class="pct">'+(sec.breadth*100).toFixed(0)+'%</span></div>');
  }
  document.getElementById('sectList').innerHTML=sh.join('');
  var ip=[];
  for(var q=0;q<DATA.ipos.length;q++){
    var o=DATA.ipos[q];
    ip.push('<button class="row"><div class="rk">'+(q+1)+'</div><div class="bd">'
      +'<div class="sym">'+esc(o.symbol)+'</div>'
      +'<div class="sub">'+esc(o.sector)+' \u00b7 listed '+esc(o.listed_date)+'</div>'
      +'<div class="stats">first-week high <b>'+F.rs(o.week_high)+'</b> \u00b7 now <b>'
      +F.rs(o.price)+'</b> \u00b7 '+F.cr(o.market_cap_cr)
      +(o.week_rs!=null?' \u00b7 1-week vs market <b>'+F.spct(o.week_rs,1)+'</b>':'')
      +'</div><div class="stats">'+(o.holds_week_high?'Holding above its first-week high'
        :'Below its first-week high, but outpacing the market this week')+'</div></div>'
      +'<div class="rt"><div class="big '+(o.above_week_high>=0?'up':'down')+'">'
      +F.spct(o.above_week_high,1)+'</div>'
      +'<div class="sub">vs first week</div></div></button>');
  }
  document.getElementById('ipoList').innerHTML=ip.length?ip.join(''):
    '<div class="empty">No recent listings are holding above their first-week high.</div>';
  candidates();
}
if(document.readyState==='loading'){
  document.addEventListener('DOMContentLoaded',boot);
}else{boot();}
"""

TEMPLATE = """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Momentum book</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Manrope:wght@500;700;800&display=swap" rel="stylesheet">
<style>__CSS__</style>
</head><body><div class="wrap">

<div class="mast">
  <h1>Momentum book</h1>
  <div class="stamp">__STAMP__ &nbsp;&middot;&nbsp; __UNIVERSE__ screened &nbsp;&middot;&nbsp; __ELIGIBLE__ qualified</div>
</div>

<div class="regime __RCLASS__">
  <div class="kicker">__RSTATE__</div>
  <div class="line">__RDETAIL__</div>
  <div class="facts">
    <div class="fact"><b>__INVESTED__</b><span>capital deployed</span></div>
    <div class="fact"><b>__POSN__</b><span>positions to run</span></div>
    <div class="fact"><b>__GAP__</b><span>index vs 200-day</span></div>
    <div class="fact"><b>__VIX__</b><span>India VIX</span></div>
  </div>
</div>

<div class="tabs" role="tablist">
  <button class="tab" role="tab" aria-selected="true" data-panel="p-exit">Exiting<span class="pill __EHOT__">__NEXIT__</span></button>
  <button class="tab" role="tab" aria-selected="false" data-panel="p-entry">Entering<span class="pill">__NBUY__</span></button>
  <button class="tab" role="tab" aria-selected="false" data-panel="p-signal">New signals<span class="pill">__NSIG__</span></button>
  <button class="tab" role="tab" aria-selected="false" data-panel="p-book">The book<span class="pill">__NBOOK__</span></button>
  <button class="tab" role="tab" aria-selected="false" data-panel="p-cand">Candidates<span class="pill">__NCAND__</span></button>
  <button class="tab" role="tab" aria-selected="false" data-panel="p-ipo">New listings<span class="pill">__NIPO__</span></button>
  <button class="tab" role="tab" aria-selected="false" data-panel="p-sect">Sectors</button>
</div>

<div class="panel on" id="p-exit">
  <p class="lede">Sell these on the next open. Checked daily, independent of the rebalance calendar.</p>
  <div id="exitList"></div>
</div>

<div class="panel" id="p-entry">
  <p class="lede">Buy these at the weight shown, and place the stop with your broker the same day.</p>
  <div id="entryList"></div>
</div>

<div class="panel" id="p-signal">
  <p class="lede">Names that cleared every entry rule since the last run. Not instructions &mdash; they enter the book at the next rebalance or when a seat opens.</p>
  <div id="signalList"></div>
</div>

<div class="panel" id="p-book">
  <p class="lede">Everything you hold. Tap any row for the full detail.</p>
  <div id="bookList"></div>
</div>

<div class="panel" id="p-cand">
  <p class="lede">Every name that cleared the gates, ranked. Search by symbol or sector.</p>
  <div class="controls">
    <input id="candSearch" type="search" placeholder="Search symbol or sector" aria-label="Search candidates">
    <button class="sortbtn on" data-key="rank">Rank</button>
    <button class="sortbtn" data-key="ready">Ready only</button>
    <button class="sortbtn" data-key="r12m">1-year return</button>
    <button class="sortbtn" data-key="r3m">3-month return</button>
  </div>
  <div id="candList"></div>
</div>

<div class="panel" id="p-ipo">
  <p class="lede">Mainboard listings from the last six months still trading above the high of their first week. Too young for the momentum screen &mdash; watch these, do not buy them blind.</p>
  <div id="ipoList"></div>
</div>

<div class="panel" id="p-sect">
  <p class="lede">Ranked by six-month median return and breadth. Only the top __TOPSECT__ are eligible; the bar shows the share of the sector above its 200-day average.</p>
  <div id="sectList"></div>
</div>

<footer>
Next rebalance __NEXTREB__. Scores rebuild every trading day; the book changes on a rebalance or an exit.<br>
End-of-day prices, adjusted for splits and dividends. A screening output, not advice.
</footer>
</div>
<script>const DATA=__DATA__;</script>
<script>__JS__</script>
</body></html>"""


def render(payload: dict, out_path: str) -> str:
    reg = payload["regime"]
    gap = "--"
    if reg.get("last") and reg.get("sma200"):
        gap = f'{(reg["last"] / reg["sma200"] - 1) * 100:+.1f}%'

    # The exit list is what the alerts already are; give it its own key so the
    # front end never has to know they were called alerts.
    payload = dict(payload)
    payload.setdefault("ipos", [])
    payload["exits"] = [
        {"symbol": a["symbol"], "sector": a["kind"], "name": a["detail"],
         "rank": "", "r12m": None, "catalyst": ""}
        for a in payload.get("alerts", [])
    ]

    if payload.get("warming"):
        reg = dict(reg)
        reg["state"] = "loading"
        reg["detail"] = (f'Still loading the market — {payload["pending"]} companies '
                         'left. The opening book is held back until the whole '
                         'universe is in. Re-run the workflow to continue loading.')
        payload["regime"] = reg

    n_exit = len(payload["exits"])
    n_buy = sum(1 for b in payload["book"] if b["action"] == "buy")

    html = TEMPLATE
    for k, v in {
        "__CSS__": CSS,
        "__JS__": JS,
        "__DATA__": json.dumps(payload, default=str),
        "__STAMP__": payload["stamp"],
        "__UNIVERSE__": str(payload["universe_n"]),
        "__ELIGIBLE__": str(payload["eligible_n"]),
        "__RCLASS__": {"risk-off": "bad", "defensive": "bad",
                       "caution": "warn", "loading": "warn"}.get(reg["state"], ""),
        "__RSTATE__": reg["state"].replace("-", " ").upper(),
        "__RDETAIL__": reg["detail"],
        "__INVESTED__": f'{reg["invested"] * 100:.0f}%',
        "__POSN__": str(reg["positions"]),
        "__GAP__": gap,
        "__VIX__": f'{reg["vix"]:.1f}' if reg.get("vix") else "--",
        "__EHOT__": "hot" if n_exit else "",
        "__NEXIT__": str(n_exit),
        "__NBUY__": str(n_buy),
        "__NSIG__": str(len(payload.get("new_signals", []))),
        "__NBOOK__": str(len(payload["book"])),
        "__NCAND__": str(len(payload.get("candidates", []))),
        "__NIPO__": str(len(payload.get("ipos", []))),
        "__TOPSECT__": str(payload["top_sectors"]),
        "__NEXTREB__": payload["next_rebalance"],
    }.items():
        html = html.replace(k, v)

    out_dir = os.path.dirname(out_path)
    os.makedirs(out_dir, exist_ok=True)
    # Tells GitHub Pages to serve these files as-is instead of running them
    # through Jekyll, which chokes on a plain HTML page.
    open(os.path.join(out_dir, ".nojekyll"), "a").close()
    with open(out_path, "w") as fh:
        fh.write(html)
    with open(os.path.join(os.path.dirname(out_path), "data.json"), "w") as fh:
        json.dump(payload, fh, indent=2, default=str)
    return out_path
