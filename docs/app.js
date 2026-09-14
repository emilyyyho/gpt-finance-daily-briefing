'use strict';
const $ = id => document.getElementById(id);
const escapeText = text => String(text ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const safeUrl = url => { try { const u = new URL(url); return ['https:', 'http:'].includes(u.protocol) ? u.href : '#'; } catch { return '#'; } };
const dateFormat = new Intl.DateTimeFormat('zh-CN', {timeZone:'Asia/Shanghai',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false});
const timeText = value => value && Number.isFinite(Date.parse(value)) ? dateFormat.format(new Date(value)) : '时间未知';
const dateKey = () => new Intl.DateTimeFormat('sv-SE', {timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
const statusLabels = {pending:'等待投递',sending:'发送中',sent:'接口确认成功',retry_pending:'等待重试',failed:'发送失败',uncertain:'送达待核实'};
let snapshot = null, statuses = {}, category = '全部', limit = 12, loading = false;

function sparkline(market) {
  const values = (market.history || []).map(p => p.close).filter(Number.isFinite);
  if(values.length < 2) return '<svg aria-label="历史数据不足"></svg>';
  const low = Math.min(...values), range = Math.max(...values) - low || 1;
  const points = values.map((v,i) => `${(i/(values.length-1)*180).toFixed(1)},${(29-(v-low)/range*26).toFixed(1)}`).join(' ');
  return `<svg viewBox="0 0 180 32" preserveAspectRatio="none" role="img" aria-label="近一个月日线收盘走势"><polyline points="${points}" fill="none" stroke="${values.at(-1)>=values[0]?'#cf6666':'#389c83'}" stroke-width="1.5"/></svg>`;
}

function renderMarkets() {
  $('markets').innerHTML = snapshot.markets.map(m => {
    const available = m.status === 'ok', change = m.change_pct, trend = m.five_day_pct;
    return `<article class="quote"><div class="quote-head"><strong><a href="${escapeText(safeUrl(m.url))}" target="_blank" rel="noopener noreferrer">${escapeText(m.name)} ↗</a></strong><small>${escapeText(m.unit)}</small></div>
      <div class="quote-price">${available?Number(m.price).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2}):'—'}</div>
      <div class="quote-change ${change>0?'up':change<0?'down':'neutral'}">${available && Number.isFinite(change)?`${change>=0?'+':''}${change.toFixed(2)}% 较前收盘`:'行情暂不可得'}</div>
      ${sparkline(m)}<div class="quote-time">报价 ${timeText(m.quoted_at)} · 延迟数据</div>
      <div class="trend" title="${escapeText(m.note||'')}">${Number.isFinite(trend)?`近 5 交易日 ${trend>=0?'+':''}${trend.toFixed(2)}%`:'历史数据不足'} · ${escapeText(m.source)}</div></article>`;
  }).join('');
}

function renderNews() {
  if (!snapshot) return;
  const query = $('search').value.trim().toLowerCase();
  const items = snapshot.news.filter(n => (category==='全部'||n.category===category) && `${n.title} ${n.source}`.toLowerCase().includes(query));
  $('count').textContent = `${items.length} 条`;
  $('news').innerHTML = items.slice(0,limit).map((n,i) => `<article class="news-row"><span class="rank">${i+1}</span><div><a class="news-title" href="${escapeText(safeUrl(n.url))}" target="_blank" rel="noopener noreferrer">${escapeText(n.title)}</a><div class="news-meta"><span>${escapeText(n.source)}</span><time datetime="${escapeText(n.published_at)}">${timeText(n.published_at)}</time><span class="news-category">${escapeText(n.category)}</span><span>原文 ↗</span></div>${n.summary?`<p class="news-summary">${escapeText(n.summary)}</p>`:''}</div></article>`).join('') || '<div class="empty">没有符合条件的近期新闻。可以更换分类或搜索词。</div>';
  $('more').hidden = items.length <= limit;
}

function renderSidebar() {
  const today = dateKey();
  $('delivery').innerHTML = [['am','08:00','早报'],['pm','20:00','晚报']].map(([slot,time,label]) => {
    const key = `${today}-${slot}`, entry = statuses[key];
    return `<div class="edition"><time>${time}</time><div><strong>${label}</strong><small>${entry?escapeText(statusLabels[entry.status]||entry.status):'尚未生成'}${entry?.kind==='outage'?' · 数据异常通知':''}</small></div>${entry?`<button data-report="${key}">查看</button>`:''}</div>`;
  }).join('');
  $('source-count').textContent = `${snapshot.sources.filter(s=>s.status==='ok').length}/${snapshot.sources.length} 可用`;
  $('sources').innerHTML = snapshot.sources.map(s=>`<div class="source-row" title="${escapeText(s.via)} · 检查 ${timeText(s.checked_at)}"><span class="source-name"><i class="dot ${s.status==='ok'?'ok':''}"></i>${escapeText(s.name)}</span><span class="source-status">${s.status==='ok'?`${s.count} 条近期新闻`:s.status==='empty'?'暂无近期内容':'获取失败'}</span></div>`).join('');
  const entries = Object.entries(statuses).sort(([a],[b])=>b.localeCompare(a));
  $('history').innerHTML = entries.slice(0,60).map(([key,e])=>`<div class="history-row"><span>${escapeText(key.slice(0,10))} · ${escapeText(e.label)}</span><button data-report="${escapeText(key)}">阅读 ↗</button></div>`).join('') || '<p class="small-note">首期日报将在这里归档。</p>';
  const latestToday = entries.find(([key,e])=>key.startsWith(today)&&e.ai);
  $('ai-title').textContent = latestToday ? '当期分析已归档' : '基础新闻版';
  $('ai-description').textContent = latestToday ? '可在对应早晚报中查看 AI 分析，并核对新闻来源。' : '本期 AI 分析未生成。新闻与市场数据照常更新。';
}

async function refresh() {
  if(loading) return;
  loading=true; $('refresh').disabled=true;
  try {
    const [newsResponse,statusResponse] = await Promise.all([fetch(`data/latest.json?t=${Date.now()}`,{cache:'no-store'}),fetch(`data/status.json?t=${Date.now()}`,{cache:'no-store'})]);
    if(!newsResponse.ok || !statusResponse.ok) throw Error('数据尚未发布');
    const next = await newsResponse.json();
    if(!Array.isArray(next.news)||!Array.isArray(next.markets)||!Array.isArray(next.sources)) throw Error('数据格式异常');
    statuses = await statusResponse.json(); snapshot=next;
    const age = (Date.now()-Date.parse(snapshot.generated_at))/60000;
    $('freshness').textContent = `数据快照 ${timeText(snapshot.generated_at)}${age>75?' · 更新已延迟，请谨慎使用':''}`;
    $('freshness').className = age>75?'stale':'';
    renderMarkets();renderNews();renderSidebar();
  } catch(error) {
    $('freshness').textContent = snapshot?'刷新失败，正在显示上次快照':'数据尚未发布或暂时无法读取，请稍后刷新';
    $('freshness').className='stale';
    if(!snapshot) $('news').innerHTML='<div class="empty">等待云端采集结果；不会以示例新闻替代真实资讯。</div>';
  } finally {loading=false;$('refresh').disabled=false;}
}

document.querySelectorAll('[data-category]').forEach(button=>button.addEventListener('click',()=>{category=button.dataset.category;limit=12;document.querySelectorAll('[data-category]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));renderNews();}));
$('search').addEventListener('input',()=>{limit=12;renderNews();});
$('more').addEventListener('click',()=>{limit+=12;renderNews();});
$('refresh').addEventListener('click',refresh);
document.addEventListener('click',async event=>{
  const key=event.target.closest('[data-report]')?.dataset.report;
  if(!key || !/^\d{4}-\d{2}-\d{2}-(am|pm)$/.test(key)) return;
  $('report-content').textContent='正在读取…';$('report-dialog').showModal();
  try {const response=await fetch(`reports/${key}.md`);if(!response.ok)throw Error();$('report-content').textContent=await response.text();}
  catch{$('report-content').textContent='日报读取失败，请稍后重试。';}
});
$('close-report').addEventListener('click',()=>$('report-dialog').close());
$('today').textContent=new Intl.DateTimeFormat('zh-CN',{timeZone:'Asia/Shanghai',year:'numeric',month:'long',day:'numeric',weekday:'long'}).format(new Date());
refresh();setInterval(refresh,60000);
