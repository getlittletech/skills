(function(){
var K=%KEY%,st={done:{},hide:{},view:'s',mode:'file'};
try{var v=JSON.parse(localStorage.getItem(K));if(v)st=Object.assign(st,v)}catch(e){}
function save(){try{localStorage.setItem(K,JSON.stringify(st))}catch(e){}}
var B=document.body;
function apply(){
 B.classList.toggle('split',st.view==='s');
 B.classList.toggle('m-file',st.mode==='file');B.classList.toggle('m-story',st.mode==='story');
 document.querySelectorAll('.vw[data-sw=view] button').forEach(function(b){b.classList.toggle('on',b.dataset.v===st.view)});
 document.querySelectorAll('.vw[data-sw=mode] button').forEach(function(b){b.classList.toggle('on',b.dataset.v===st.mode)});
 document.querySelectorAll('[data-k]').forEach(function(e){if(e.classList.contains('nv'))e.classList.toggle('done',!!st.done[e.dataset.k])});
 document.querySelectorAll('.dn input').forEach(function(c){c.checked=!!st.done[c.dataset.k]});
 document.querySelectorAll('.lg').forEach(function(b){b.classList.toggle('hid-t',!!st.hide[b.dataset.t]);b.style.opacity=st.hide[b.dataset.t]?.35:''});
 document.querySelectorAll('section.sec,.nv,table.matrix tr[data-t]').forEach(function(e){if(e.dataset.t)e.classList.toggle('hid',!!st.hide[e.dataset.t])});
}
document.querySelectorAll('.vw[data-sw=view] button').forEach(function(b){b.onclick=function(){st.view=b.dataset.v;save();apply()}});
document.querySelectorAll('.vw[data-sw=mode] button').forEach(function(b){b.onclick=function(){st.mode=b.dataset.v;save();apply()}});
document.querySelectorAll('.dn input').forEach(function(c){c.onchange=function(){st.done[c.dataset.k]=c.checked;save();apply()}});
document.querySelectorAll('.lg').forEach(function(b){b.onclick=function(){st.hide[b.dataset.t]=!st.hide[b.dataset.t];save();apply()}});
document.querySelectorAll('button.copy').forEach(function(b){b.onclick=function(e){e.preventDefault();
 if(navigator.clipboard)navigator.clipboard.writeText(b.dataset.copy).then(function(){b.textContent='Copied';setTimeout(function(){b.textContent='Copy'},1200)})}});
function mode(m){if(st.mode!==m){st.mode=m;save();apply()}}
function reveal(el){var p=el.parentElement;while(p){if(p.tagName==='DETAILS')p.open=true;p=p.parentElement}}
function go(el){if(!el)return;reveal(el);el.scrollIntoView({block:'start'});window.scrollBy(0,-8);
 el.classList.remove('flash');void el.offsetWidth;el.classList.add('flash')}
function inMode(sel){var c=document.getElementById(st.mode==='file'?'byfile':'bystory');return c.querySelector(sel)}
document.addEventListener('click',function(e){
 var t=e.target.closest('[data-go-story],[data-go-file],[data-go-cell],[data-go-issue],a.sym');if(!t)return;
 if(t.closest('summary'))e.preventDefault();
 if(t.dataset.goStory){mode('story');go(document.getElementById('story-'+t.dataset.goStory));return}
 if(t.dataset.goFile){mode('file');go(document.getElementById('file-'+t.dataset.goFile));return}
 if(t.dataset.goCell){var p=t.dataset.goCell.split(','),n=p[0],fi=p[1];
  if(t.dataset.mode)mode(t.dataset.mode);
  var el=st.mode==='file'?document.getElementById('f'+fi+'-'+n):document.getElementById('s'+fi+'-'+n)||document.getElementById('s'+fi+'-'+n+'x');
  if(!el){mode(st.mode==='file'?'story':'file');el=document.getElementById('f'+fi+'-'+n)||document.getElementById('s'+fi+'-'+n)}
  go(el);return}
 if(t.dataset.goIssue){var q='[data-issue="'+t.dataset.goIssue+'"]',tb=B.classList.contains('split')?'table.s ':'table.u ';
  var el=inMode(tb+q)||inMode(q);
  if(!el){mode(st.mode==='file'?'story':'file');el=inMode(tb+q)||inMode(q)}
  if(el&&el.tagName==='DETAILS')el.open=true;go(el);return}
 if(t.classList.contains('sym')){var nm=t.dataset.sym,tbl=B.classList.contains('split')?'table.s':'table.u';
  var el=inMode(tbl+' [data-def="'+nm+'"]');
  if(!el){mode('file');el=inMode(tbl+' [data-def="'+nm+'"]')}
  go(el)}
});
var S=function(){return [].slice.call(document.querySelectorAll((st.mode==='file'?'#byfile':'#bystory')+' section.sec:not(.hid)'))};
function cur(){var y=scrollY+90,c=0;S().forEach(function(s,i){if(s.offsetTop<=y)c=i});return c}
addEventListener('scroll',function(){var s=S()[cur()];if(!s)return;
 document.querySelectorAll('.nv').forEach(function(a){a.classList.toggle('on',a.dataset.k===s.dataset.k)})});
addEventListener('keydown',function(e){if(e.target.tagName==='INPUT'||e.metaKey||e.ctrlKey||e.altKey)return;var s=S(),i=cur();
 if(e.key==='j'&&s[i+1])s[i+1].scrollIntoView();if(e.key==='k'&&s[i-1])s[i-1].scrollIntoView();
 if(e.key==='f'){mode(st.mode==='file'?'story':'file')}
 if(e.key==='s'){st.view=st.view==='s'?'u':'s';save();apply()}
 if(e.key==='e'&&s[i]){var d=s[i].querySelectorAll('details.ex'),o=![].some.call(d,function(x){return x.open});d.forEach(function(x){x.open=o})}
 if(e.key==='x'&&s[i]){var c=s[i].querySelector('.dn input');if(c){c.checked=!c.checked;c.onchange()}}});
apply();
})();
