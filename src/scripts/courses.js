// Course search: filter the sample catalogue and compare up to three courses.
// The catalogue is placeholder data, labelled as such on the page.
import { $, fill, load, save, daysUntil, untilText, toolData } from './lib.js';

const T = toolData();
const FIELDS = T.FIELDS, COURSES = T.COURSES;
function money(n){return n===0?"No tuition":n.toLocaleString()}
var S=load("u500-s",{shortlist:[]});
function persistS(){save("u500-s",S)}

/* ---------- the spec row, shared by matches and search ---------- */
function specRow(c){
  var total=c.fee*c.yr + c.live*12*c.yr;
  var d=daysUntil(c.dl);
  var cells=[
    ["Whole course", total.toLocaleString(), c.yr+(c.yr===1?" year":" years")+" of fees and living"],
    ["Tuition", c.fee===0?"None":c.fee.toLocaleString(), c.fee===0?"at a public university":"a year"],
    ["Living", c.live.toLocaleString(), "a month"],
    ["Applications close", c.dl, untilText(c.dl), d!==null&&d<60],
    ["English", "IELTS "+c.ielts, c.sch==="Several"?"scholarships available":"few scholarships"]
  ];
  var g=document.createElement("div");g.className="spec";
  cells.forEach(function(x){
    var wrap=document.createElement("div");
    var dt=document.createElement("dt");dt.textContent=x[0];
    var dd=document.createElement("dd");dd.textContent=x[1];
    if(x[3])dd.className="soon";
    var sm=document.createElement("small");sm.textContent=x[2];
    dd.appendChild(sm);
    wrap.appendChild(dt);wrap.appendChild(dd);g.appendChild(wrap);
  });
  return g;
}

/* ---------- shortlist, shared by search, matches and the writing tools ---------- */
function shortBtn(name,after){
  var on=S.shortlist.indexOf(name)>=0;
  var b=document.createElement("button");
  b.type="button";b.className="cmp";
  b.textContent=on?"Shortlisted":"Shortlist";
  b.setAttribute("aria-pressed",String(on));
  b.addEventListener("click",function(){
    function flip(){
      var i=S.shortlist.indexOf(name);
      if(i>=0)S.shortlist.splice(i,1);else S.shortlist.push(name);
      persistS();
      if(after)after();
    }
    flip();
  });
  return b;
}

/* ---------- course search ---------- */
var CS={field:"",country:"",level:"",fee:40000,ielts:"",sch:false,pick:[]};
var IELTS_OPTS=[{l:"Any requirement",v:""},{l:"6.0 or below",v:"6"},{l:"6.5 or below",v:"6.5"},{l:"7.0 or below",v:"7"}];
fill($("cs-field"),["All fields"].concat(FIELDS));
fill($("cs-country"),["All destinations"].concat(COURSES.map(function(c){return c.c}).filter(function(v,i,a){return a.indexOf(v)===i}).sort()));
fill($("cs-level"),["All levels","Bachelor","Masters"]);
fill($("cs-ielts"),IELTS_OPTS);
function csRows(){
  return COURSES.filter(function(c){
    if(CS.field&&CS.field!=="All fields"&&c.acc.indexOf(CS.field)<0)return false;
    if(CS.country&&CS.country!=="All destinations"&&c.c!==CS.country)return false;
    if(CS.level&&CS.level!=="All levels"&&c.lvl!==CS.level)return false;
    if(c.fee>CS.fee)return false;
    if(CS.ielts&&c.ielts>Number(CS.ielts))return false;
    if(CS.sch&&c.sch==="Few")return false;
    return true;
  });
}
function renderSearch(){
  var rows=csRows();
  $("cs-fee-out").textContent=Number(CS.fee).toLocaleString();
  $("cs-tally").textContent="";
  var b=document.createElement("b");b.textContent=rows.length+(rows.length===1?" course":" courses");
  $("cs-tally").appendChild(b);
  $("cs-tally").appendChild(document.createTextNode(" of "+COURSES.length+" match your filters"));

  var box=$("cs-list");box.textContent="";
  if(!rows.length){
    var e=document.createElement("p");e.className="empty";
    e.textContent="Nothing matches. Widen the tuition range or clear a filter.";box.appendChild(e);
  }
  rows.forEach(function(c){
    var d=document.createElement("article");d.className="chit";
    var top=document.createElement("div");top.className="chit-top";
    var left=document.createElement("div");
    var h=document.createElement("h3");h.textContent=c.n;
    var w=document.createElement("div");w.className="where";w.textContent=c.u+", "+c.c;
    left.appendChild(h);left.appendChild(w);
    var acts=document.createElement("div");acts.style.cssText="display:flex;gap:.35rem;flex:none;flex-wrap:wrap;justify-content:flex-end";
    var on=CS.pick.indexOf(c.n)>=0;
    var btn=document.createElement("button");btn.type="button";btn.className="cmp";
    btn.textContent=on?"Comparing":"Compare";btn.setAttribute("aria-pressed",String(on));
    btn.addEventListener("click",function(){
      var i=CS.pick.indexOf(c.n);
      if(i>=0)CS.pick.splice(i,1);
      else if(CS.pick.length<3)CS.pick.push(c.n);
      renderSearch();
    });
    acts.appendChild(shortBtn(c.n,renderSearch));
    acts.appendChild(btn);
    top.appendChild(left);top.appendChild(acts);d.appendChild(top);
    d.appendChild(specRow(c));box.appendChild(d);
  });
  renderTray();
}
function renderTray(){
  var picked=COURSES.filter(function(c){return CS.pick.indexOf(c.n)>=0});
  $("cs-tray-say").textContent = picked.length
    ? picked.length+" of 3 selected. Rows that differ are what should decide it."
    : "Pick up to three courses above to line them up row by row.";
  var box=$("cs-tray");box.textContent="";
  if(!picked.length)return;
  var wrap=document.createElement("div");wrap.className="tbl-wrap";
  var t=document.createElement("table");t.className="tbl";
  var thead=document.createElement("thead");var hr=document.createElement("tr");
  hr.appendChild(document.createElement("th"));
  picked.forEach(function(c){var th=document.createElement("th");th.textContent=c.n;hr.appendChild(th)});
  thead.appendChild(hr);t.appendChild(thead);
  var tb=document.createElement("tbody");
  [["Destination",function(c){return c.c}],
   ["Length",function(c){return c.yr+(c.yr===1?" year":" years")}],
   ["Tuition a year",function(c){return money(c.fee)}],
   ["Living a month",function(c){return c.live.toLocaleString()}],
   ["Whole course",function(c){return (c.fee*c.yr+c.live*12*c.yr).toLocaleString()}],
   ["English",function(c){return "IELTS "+c.ielts}],
   ["Next deadline",function(c){return c.dl}],
   ["Scholarships",function(c){return c.sch}],
   ["Work rights",function(c){return c.workrights}]].forEach(function(r){
    var tr=document.createElement("tr");
    var td0=document.createElement("td");td0.textContent=r[0];tr.appendChild(td0);
    var vals=picked.map(r[1]);
    var same=vals.every(function(v){return v===vals[0]});
    vals.forEach(function(v){
      var td=document.createElement("td");td.textContent=v;
      if(!same&&picked.length>1)td.style.fontWeight="600";
      tr.appendChild(td);
    });
    tb.appendChild(tr);
  });
  t.appendChild(tb);wrap.appendChild(t);box.appendChild(wrap);
}
[["cs-field","field"],["cs-country","country"],["cs-level","level"],["cs-ielts","ielts"]].forEach(function(p){
  $(p[0]).addEventListener("change",function(){CS[p[1]]=this.value;renderSearch()});
});
$("cs-fee").addEventListener("input",function(){CS.fee=Number(this.value);renderSearch()});
$("cs-sch").addEventListener("change",function(){CS.sch=this.checked;renderSearch()});
$("cs-reset").addEventListener("click",function(){
  CS.field="";CS.country="";CS.level="";CS.fee=40000;CS.ielts="";CS.sch=false;
  $("cs-field").selectedIndex=0;$("cs-country").selectedIndex=0;$("cs-level").selectedIndex=0;
  $("cs-ielts").selectedIndex=0;$("cs-fee").value=40000;$("cs-sch").checked=false;
  renderSearch();
});
renderSearch();
renderSearch();
