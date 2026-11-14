// Course fitment: four questions, then the sample courses scored against the answers.
// The courses and the scoring model are placeholders, labelled as such on the page.
import { $, fill, load, save, daysUntil, untilText, toolData } from './lib.js';

const T = toolData();
const FIELDS = T.FIELDS, GOALS = T.GOALS, GRADES = T.GRADES, YEARS = T.YEARS, NATS = T.NATS, BUDGETS = T.BUDGETS;
const DEST = T.DEST, REL = T.REL, GREL = T.GREL, COURSES = T.COURSES;
function money(n){return n===0?"No tuition":n.toLocaleString()}
function yearsNum(v){return {"None":0,"Under a year":0.5,"1 to 2 years":1.5,"3 to 5 years":4,"More than 5":6}[v]||0}
var S=load("u500-s",{shortlist:[]});
function persistS(){save("u500-s",S)}

var ENVS=["Must live in English","Happy either way","Keen to learn a language"];
var A={nat:"India",level:"Bachelor",grade:"Above average",sfield:FIELDS[0],lang:"0",score:"",
       wfield:FIELDS[0],years:"None",goal:GOALS[0],line:"",budget:15000,homeField:FIELDS[0],
       env:"Happy either way"};
function isEnglishCountry(name){
  for(var i=0;i<DEST.length;i++){if(DEST[i].c===name)return !!DEST[i].eng}
  return false;
}
try{var saved=localStorage.getItem("u500-fit");if(saved){A=Object.assign(A,JSON.parse(saved))}}catch(e){}
function persist(){try{localStorage.setItem("u500-fit",JSON.stringify(A))}catch(e){}}
var step=0,STEPS=[
  {k:"About you",t:"About you",s:"Nothing here is sent anywhere. It only shapes your match scores."},
  {k:"Study",t:"What you’ve studied",s:"Your prior field is the single biggest factor in whether a course will admit you."},
  {k:"Work",t:"Work you’ve done",s:"Some courses expect experience. Others prefer you fresh out of a degree."},
  {k:"Goal",t:"Your goal",s:"The last one. This is what separates a good match from a convenient one."}
];
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

/* ---------- quiz build ---------- */
fill($("q-nat"),NATS,A.nat);
fill($("q-sfield"),FIELDS,A.sfield);
fill($("q-wfield"),FIELDS,A.wfield);
fill($("q-years"),YEARS,A.years);
fill($("q-goal"),GOALS,A.goal);
$("q-level").value=A.level;
$("q-lang").value=A.lang;
$("q-score").value=A.score;
$("q-line").value=A.line;

function segGroup(boxId,values,key){
  var box=$(boxId);box.textContent="";
  values.forEach(function(v){
    var b=document.createElement("button");
    b.type="button";b.className="seg";b.textContent=v;
    b.setAttribute("aria-pressed",String(A[key]===v));
    b.addEventListener("click",function(){
      A[key]=v;persist();
      box.querySelectorAll(".seg").forEach(function(x){x.setAttribute("aria-pressed",String(x===b))});
    });
    box.appendChild(b);
  });
}
segGroup("q-grade",GRADES,"grade");
segGroup("q-env",ENVS,"env");

[["q-nat","nat"],["q-level","level"],["q-sfield","sfield"],["q-lang","lang"],["q-score","score"],
 ["q-wfield","wfield"],["q-years","years"],["q-goal","goal"],["q-line","line"]].forEach(function(p){
  var el=$(p[0]);
  el.addEventListener("input",function(){A[p[1]]=el.value;persist()});
  el.addEventListener("change",function(){A[p[1]]=el.value;persist()});
});

function drawStamps(){
  var box=$("stamps");box.textContent="";
  STEPS.forEach(function(s,i){
    var b=document.createElement("button");
    b.type="button";b.className="sslot";
    b.dataset.state=i<step?"done":(i===step?"now":"todo");
    b.innerHTML='<span>'+(i+1)+' of 4</span><b>'+s.k+'</b>'+
      '<svg class="ink" width="26" height="26" viewBox="0 0 26 26" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2">'+
      '<circle cx="13" cy="13" r="11"/><path d="M7.5 13.5l3.5 3.5 7.5-8"/></svg>';
    if(i<step){b.addEventListener("click",function(){step=i;renderStep()})}
    else{b.disabled=i>step}
    if(i===step)b.setAttribute("aria-current","step");
    box.appendChild(b);
  });
}
function renderStep(){
  document.querySelectorAll(".q-step").forEach(function(f){f.hidden=Number(f.dataset.step)!==step});
  $("q-title").textContent=STEPS[step].t;
  $("q-sub").textContent=STEPS[step].s;
  $("q-back").textContent=step===0?"Back to start":"Back";
  $("q-next").textContent=step===3?"See my matches":"Next";
  drawStamps();
}
$("q-next").addEventListener("click",function(){
  if(step<3){step++;renderStep();window.scrollTo(0,0)}
  else{step=4;drawStamps();showView("results");renderResults()}
});
$("q-back").addEventListener("click",function(){
  if(step===0){location.href="/"}else{step--;renderStep()}
});

/* ---------- scoring ---------- */
function score(c){
  var studyRaw = c.acc.indexOf(A.sfield)>=0 ? 40
    : (REL[A.sfield]||[]).some(function(r){return c.acc.indexOf(r)>=0}) ? 25 : 10;
  var gradeFactor = A.grade==="Top of class"?1:(A.grade==="Above average"?0.92:0.8);
  var study=Math.round(studyRaw*gradeFactor);

  var workBase = c.work.indexOf(A.wfield)>=0 ? 15
    : (REL[A.wfield]||[]).some(function(r){return c.work.indexOf(r)>=0}) ? 9 : 3;
  var y=yearsNum(A.years);
  var yearPart = c.exp===0 ? (y>0?10:8) : Math.min(10,Math.round(10*y/c.exp));
  var work=Math.min(25,workBase+yearPart);

  var goal = c.out.indexOf(A.goal)>=0 ? 35
    : (GREL[A.goal]||[]).some(function(g){return c.out.indexOf(g)>=0}) ? 20 : 5;

  return {study:study,work:work,goal:goal,total:study+work+goal,
          fieldOk:studyRaw>=25,workOk:work>=18,goalOk:goal>=20};
}
function blockers(c){
  var out=[];
  if(c.fee>A.budget)out.push("Tuition is above the "+A.budget.toLocaleString()+" you set");
  var s=parseFloat(A.score);
  if(A.lang==="0")out.push("Needs IELTS "+c.ielts+" and you haven’t sat it");
  else if(!isNaN(s)&&s<c.ielts)out.push("Needs IELTS "+c.ielts+", you have "+s);
  if(c.lvl==="Masters"&&A.level==="Secondary school")out.push("Masters entry needs a bachelor first");
  return out;
}
function nextMove(c,sc,bl){
  if(bl.length)return bl[0].indexOf("IELTS")>=0?"Book your English test. It gates this one entirely.":
    (bl[0].indexOf("Tuition")>=0?"Either raise your budget or look at the tuition-free options above.":bl[0]+".");
  if(!sc.fieldOk)return "Your prior field isn’t a usual entry route. Explain the link in your statement, or look at a bridging course.";
  if(!sc.workOk)return c.exp>0?"This one expects roughly "+c.exp+(c.exp===1?" year":" years")+" of related work. Build that, or pick a course that doesn’t.":"Add a project or internship you can point to.";
  if(!sc.goalOk)return "This course doesn’t lead straight to "+A.goal+". Check the graduate destinations before you commit.";
  return "Nothing blocking. Start the application file and watch the "+c.dl+" deadline.";
}

function renderResults(){
  /* A language-environment mismatch is a preference, not an eligibility rule, so it never
     touches the 40/25/35 score. It only sinks a course below equally-eligible alternatives. */
  var ranked=COURSES.map(function(c){
    var engC=isEnglishCountry(c.c);
    return {c:c,sc:score(c),bl:blockers(c),
            envMiss:A.env==="Must live in English"&&!engC,
            envWin:A.env==="Keen to learn a language"&&!engC,
            engC:engC};
  }).sort(function(a,b){
    if(a.bl.length!==b.bl.length)return a.bl.length-b.bl.length;
    if(a.envMiss!==b.envMiss)return a.envMiss?1:-1;
    if(b.sc.total!==a.sc.total)return b.sc.total-a.sc.total;
    /* equal fit is common with a 40/25/35 model, so break the tie on something the
       student actually cares about: what the whole course costs, then how soon it closes. */
    var ca=a.c.fee*a.c.yr+a.c.live*12*a.c.yr, cb=b.c.fee*b.c.yr+b.c.live*12*b.c.yr;
    if(ca!==cb)return ca-cb;
    var da=daysUntil(a.c.dl), db=daysUntil(b.c.dl);
    return (da===null?9999:da)-(db===null?9999:db);
  });

  var clear=ranked.filter(function(r){return !r.bl.length});
  var top=ranked[0];

  $("r-title").textContent=A.line?"Matches for “"+A.line+"”":"Your matches";
  $("r-sub").textContent="Ranked by fit, with anything that blocks you today listed first. "+
    clear.length+" of "+ranked.length+" sample courses have nothing standing in your way.";

  var ro=$("readout");ro.textContent="";
  var n=document.createElement("span");n.className="readout-n";n.textContent=top.sc.total;
  var p=document.createElement("p");
  var strong=document.createElement("b");strong.textContent=top.c.n+", "+top.c.c+". ";
  p.appendChild(strong);
  p.appendChild(document.createTextNode(
    top.sc.total>=75?"Clear thread from what you’ve studied to where you want to end up. This is the story a visa officer wants to read.":
    top.sc.total>=55?"A workable fit, but you’ll have to explain a gap or two in your statement of purpose.":
    "Your strongest match is still a stretch. Consider building relevant experience, or widening the field you’ll study."));
  ro.appendChild(n);ro.appendChild(p);

  var box=$("matches");box.textContent="";
  ranked.forEach(function(r,i){
    var c=r.c,sc=r.sc,bl=r.bl;
    var d=document.createElement("article");
    d.className="match"+(i===0?" top":"");

    var head=document.createElement("div");head.className="match-head";
    var left=document.createElement("div");left.style.minWidth="0";
    var h=document.createElement("h3");h.textContent=c.n;
    var w=document.createElement("div");w.className="where";w.textContent=c.u+", "+c.c;
    left.appendChild(h);left.appendChild(w);

    var fit=document.createElement("div");fit.className="fit";
    var fb=document.createElement("b");fb.textContent=sc.total;
    var fi=document.createElement("i");fi.textContent="fit";
    fit.appendChild(fb);fit.appendChild(fi);
    var bar=document.createElement("div");bar.className="fitbar";
    [[sc.study,40],[sc.work,25],[sc.goal,35]].forEach(function(p){
      var seg=document.createElement("span");
      seg.style.flex=p[1];
      seg.firstChild;
      seg.style.setProperty("--w",Math.round(100*p[0]/p[1])+"%");
      var inner=document.createElement("i");
      inner.style.cssText="display:block;height:100%;border-radius:99px;background:var(--solid);width:"+Math.round(100*p[0]/p[1])+"%";
      seg.appendChild(inner);
      bar.appendChild(seg);
    });
    fit.appendChild(bar);
    var fn=document.createElement("div");fn.className="fit-note";
    fn.textContent="study "+sc.study+" / work "+sc.work+" / goal "+sc.goal;
    fit.appendChild(fn);
    head.appendChild(left);head.appendChild(fit);
    d.appendChild(head);

    var ban=document.createElement("div");
    ban.className="banner "+(bl.length?"bad":"ok");
    var ico=document.createElementNS("http://www.w3.org/2000/svg","svg");
    ico.setAttribute("width","15");ico.setAttribute("height","15");
    ico.setAttribute("viewBox","0 0 16 16");ico.setAttribute("fill","none");
    ico.setAttribute("stroke","currentColor");ico.setAttribute("stroke-width","1.8");
    ico.setAttribute("aria-hidden","true");
    var pth=document.createElementNS("http://www.w3.org/2000/svg","path");
    pth.setAttribute("d", bl.length ? "M8 1.5 15 14H1zM8 6.5v3.2M8 11.6v.1" : "M2.5 8.5l3.5 3.5L13.5 4");
    pth.setAttribute("stroke-linecap","round");pth.setAttribute("stroke-linejoin","round");
    ico.appendChild(pth);ban.appendChild(ico);
    var bt=document.createElement("div");
    if(bl.length===1)bt.textContent=bl[0];
    else if(bl.length>1){
      bt.appendChild(document.createTextNode(bl.length+" things stand in the way"));
      var ul=document.createElement("ul");
      bl.forEach(function(x){var li=document.createElement("li");li.textContent=x;ul.appendChild(li)});
      bt.appendChild(ul);
    } else bt.textContent="Eligible on today\u2019s answers";
    ban.appendChild(bt);
    d.appendChild(ban);

    d.appendChild(specRow(c,r));

    var mv=document.createElement("p");mv.className="move";
    var mb=document.createElement("b");mb.textContent="Next best move. ";
    mv.appendChild(mb);mv.appendChild(document.createTextNode(nextMove(c,sc,bl)));
    d.appendChild(mv);

    var act=document.createElement("div");act.style.cssText="margin-top:.8rem";
    act.appendChild(shortBtn(c.n,renderResults));
    d.appendChild(act);

    box.appendChild(d);
  });
}

/* ---------- the two views of this page ---------- */
function showView(id){
  $("quiz").hidden=id!=="quiz";
  $("results").hidden=id!=="results";
  try{history.replaceState(null,"",id==="results"?"#results":location.pathname)}catch(e){}
  window.scrollTo(0,0);
}
fill($("q-budget"),BUDGETS,A.budget);
$("q-budget").addEventListener("change",function(){A.budget=Number(this.value);persist()});
$("r-edit").addEventListener("click",function(){step=0;renderStep();showView("quiz")});
$("r-home").addEventListener("click",function(){location.href="/"});
renderStep();
if(location.hash==="#results"){step=4;drawStamps();showView("results");renderResults()}
