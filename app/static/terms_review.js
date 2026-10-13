(() => {
  "use strict";
  const host = window.ariadneTermsGraph, review = host.data.review;
  if (!review?.online) return;
  const sid = review.snapshot_id, base = "/ui/terms-review";
  const labels = {type:"Тип",role:"Роль",origin:"Происхождение"};
  const actions = {confirm:"Подтвердить",correct:"Исправить",reject:"Отклонить",uncertain:"Оставить неопределённым",restore:"Восстановить версию"};
  const make = (tag, text, attrs={}) => {
    const n=document.createElement(tag);if(text!==undefined)n.textContent=text;
    for(const [k,v] of Object.entries(attrs))n.setAttribute(k,v);return n;
  };
  const field=(text,node)=>{const l=make("label",text);l.append(node);return l;};
  const option=(select,value,label)=>select.append(make("option",label,{value}));
  const style=make("style",`#review-bar{margin:0 0 18px;padding:16px;border:1px solid var(--line);border-radius:14px;background:var(--panel)}.review-row{display:flex;gap:12px;align-items:center;flex-wrap:wrap}.review-row label{display:flex;gap:8px;align-items:center;font-size:12px}.review-note{color:var(--muted);font-size:12px;margin:9px 0}.review-error{color:#f2b3a7;white-space:pre-wrap}.review-form{border-top:1px solid var(--line);padding:16px 0;margin:12px 0}.review-form label{display:block;font-size:12px;margin:8px 0}.review-form select,.review-form textarea,.review-form input{display:block;width:100%;margin:5px 0}.review-form textarea{background:var(--bg);color:var(--text);border:1px solid var(--line);border-radius:8px;min-height:70px;padding:9px;font:inherit}.review-form button{margin:7px 5px 0 0;font-size:12px}.review-history{font-size:12px;color:var(--muted);overflow-wrap:anywhere}.review-queue-list{display:flex;gap:7px;flex-wrap:wrap;max-height:190px;overflow:auto;padding-top:10px}.review-queue-list button{font-size:12px;max-width:300px;text-align:left}#review-status{font-size:12px;margin-top:8px}.review-form select[multiple]{min-height:105px}`);
  document.head.append(style);
  const bar=make("section",undefined,{id:"review-bar"});
  bar.append(make("h2","Сохраняемый review Terms"),make("p","Решения сохраняются отдельно от источников и исходных предложений. Reviewer — заявленная личность; независимая научная приёмка не установлена.",{class:"review-note"}));
  const controls=make("div",undefined,{class:"review-row"}),view=make("select",undefined,{id:"review-view"});
  for(const [value,label] of Object.entries({effective:"Предложения + решения",proposals:"Исходные предложения",reviewed:"Решения / без решения"}))option(view,value,label);
  view.value=review.mode;controls.append(field("Показать",view));
  const axis=make("select",undefined,{id:"queue-axis"});for(const key of Object.keys(labels))option(axis,key,labels[key]);
  const queue=make("select",undefined,{id:"queue-kind"});for(const [key,label] of Object.entries({conflicts:"Конфликты",unknown:"Неопределённые",all:"Все без окончательного решения"}))option(queue,key,label);
  controls.append(field("Очередь",axis),queue,make("a","Экспорт решений и истории ↗",{href:`${base}/export?snapshot=${sid}`,target:"_blank"}));
  bar.append(controls);
  const queueArea=make("details"),queueLabel=make("summary","Очередь review"),queueList=make("div",undefined,{class:"review-queue-list"});
  queueArea.append(queueLabel,queueList);bar.append(queueArea);
  const status=make("p",review.problems.join(" "),{id:"review-status",role:review.problems.length?"alert":"status"});bar.append(status);
  if(Object.keys(review.diff.changed_inputs).length || review.diff.changed_dependencies.length){
    bar.append(make("p",`Требует повторной проверки: inputs ${Object.keys(review.diff.changed_inputs).join(", ")||"без изменений"}; зависимости ${review.diff.changed_dependencies.join(", ")||"без изменений"}; targets +${review.diff.targets_added} / −${review.diff.targets_removed}. Решения автоматически не перенесены.`,{class:"review-note"}));
  }
  document.querySelector(".workspace").before(bar);
  let queueTarget=null,currentTerm=null;
  const storageKey=`ariadne-terms-view:${sid}`;
  function remember(){sessionStorage.setItem(storageKey,JSON.stringify({article:host.state.article,term:host.state.term,mode:host.state.mode,sort:host.state.sort,kind:host.state.kind}));}
  async function readState(term=null){
    const params=new URLSearchParams({snapshot:sid,axis:axis.value,queue:queue.value});if(term)params.set("term",term);
    const response=await fetch(`${base}/state?${params}`);const result=await response.json();
    if(!response.ok)throw new Error(result.detail || `HTTP ${response.status}`);return result;
  }
  async function refreshQueue(){
    try{
      const state=await readState();queueLabel.textContent=`Очередь review · ${state.queue.length} terms`;queueList.replaceChildren();
      for(const item of state.queue){
        const b=make("button",`${item.label} · ${item.title}`,{type:"button"});
        b.addEventListener("click",()=>{queueTarget=item.assignment_ids[0];host.state.mode=axis.value;host.state.kind=null;host.chooseTerm(item.term_id);});queueList.append(b);
      }
    }catch(error){status.textContent=String(error);status.className="review-error";}
  }
  axis.addEventListener("change",refreshQueue);queue.addEventListener("change",refreshQueue);
  view.addEventListener("change",()=>{remember();const url=new URL(location.href);url.searchParams.set("view",view.value);location.href=url.href;});
  async function renderForm(article,term){
    currentTerm=term.term_id;
    const panel=make("section",undefined,{class:"review-form",id:"term-review-form"});
    panel.append(make("h3","Решение по выбранному term / употреблению"));
    const target=make("select",undefined,{id:"review-target"});option(target,`relevance:${term.term_id}`,"Релевантность term целиком");
    const mentions=new Map(article.mentions.map(m=>[m.mention_id,m.source]));
    const assignments=article.assignments.filter(a=>a.term_id===term.term_id);
    for(const a of assignments){const m=mentions.get(a.mention_id);option(target,`classification:${a.assignment_id}`,`${labels[a.axis]} · стр. ${m.page_number} [${m.start}, ${m.end}) · ${a.state}`);}
    const preferred=queueTarget && assignments.find(a=>a.assignment_id===queueTarget);
    const defaultTarget=preferred || assignments.find(a=>a.axis===(labels[host.state.mode]?host.state.mode:"type"));
    if(defaultTarget)target.value=`classification:${defaultTarget.assignment_id}`;queueTarget=null;
    const category=make("select",undefined,{id:"review-categories",multiple:"multiple","aria-label":"Категории решения"});
    const action=make("select",undefined,{id:"review-action"});for(const [value,label] of Object.entries(actions))option(action,value,label);
    const reason=make("textarea",undefined,{id:"review-reason",required:"required",placeholder:"Основание решения по точному контексту…"});
    const reviewer=make("input",undefined,{id:"reviewer",required:"required",placeholder:"Имя reviewer"});reviewer.value=localStorage.getItem("ariadne-terms-reviewer")||"";
    const kind=make("select",undefined,{id:"reviewer-kind"});option(kind,"human","Человек — заявлено");option(kind,"assistant","Агент — заявлено");
    const restore=make("select",undefined,{id:"review-restore"}),info=make("p",undefined,{class:"review-note"}),message=make("p",undefined,{role:"status"});
    const sourcePreview=make("details"),sourceLabel=make("summary","Контекст выбранного употребления"),sourceText=make("pre",undefined,{class:"selected-review-context"});
    sourceText.style.maxHeight="180px";sourceText.style.overflow="auto";
    sourcePreview.append(sourceLabel,sourceText);
    const save=make("button","Сохранить решение",{type:"button",id:"review-save"}),reload=make("button","Обновить страницу",{type:"button"});
    save.disabled=true;target.disabled=true;
    reload.addEventListener("click",()=>{remember();location.reload();});
    const historyBox=make("details",undefined,{class:"review-history"});historyBox.append(make("summary","История и прежние снимки"));
    panel.append(field("Проверяется",target),sourcePreview,info,field("Действие",action),field("Категория: можно выбрать несколько",category),field("Версия для восстановления",restore),field("Почему",reason),field("Reviewer",reviewer),field("Кто",kind),save,reload,message,historyBox);
    document.getElementById("detail").insertBefore(panel,document.querySelector("#detail .classification-evidence"));
    let state;
    try{state=await readState(term.term_id);}catch(error){message.textContent=String(error);save.disabled=true;return;}
    if(currentTerm!==term.term_id || !panel.isConnected)return;
    target.disabled=false;
    function update(){
      const [targetKind,id]=target.value.split(":"),assignment=assignments.find(a=>a.assignment_id===id),last=state.decisions[target.value];
      const use=article.uses.find(u=>assignment?u.use_id===assignment.use_id:u.use_id===term.use_ids[0]);
      const selectedContext=article.contexts.find(c=>c.context_id===use.context_id);
      sourceLabel.textContent=`${targetKind==="relevance"?"Одно из употреблений term":"Контекст выбранного употребления"} · ${selectedContext.kind} · стр. ${selectedContext.source.page_number}`;
      sourceText.textContent=selectedContext.source.quote;
      panel.dataset.expectedRevision=last?.revision||0;info.textContent=`Текущая ревизия: ${last?.revision||0}. ${last?`${last.action} · ${last.reviewer_kind}:${last.reviewer}`:"Решение отсутствует."}`;
      category.replaceChildren();
      if(assignment){
        const selected=last?.categories || (new Set(assignment.proposals.map(p=>p.category)).size===1?[assignment.proposals[0].category]:[]);
        for(const [value,label] of Object.entries(host.data.taxonomy.categories[assignment.axis])){
          if(["unclassified","unresolved","review_rejected","unreviewed","term_rejected"].includes(value))continue;
          const node=make("option",label,{value});node.selected=selected.includes(value);category.append(node);
        }
      }
      category.disabled=targetKind==="relevance";
      restore.replaceChildren();option(restore,"","Выберите прежнюю ревизию");
      const events=state.events.filter(e=>e.target_kind===targetKind&&e.target_id===id);
      for(const e of events)option(restore,String(e.revision),`rev ${e.revision} · ${e.action} · ${e.created_at}`);
      historyBox.querySelectorAll("p").forEach(n=>n.remove());
      for(const e of [...events,...state.historical_annotations.filter(e=>e.target_kind===targetKind&&e.axis===(assignment?.axis||"relevance"))]){
        historyBox.append(make("p",`${e.snapshot_id===sid?"Текущий":"Прежний снимок — требует повторной проверки"} · rev ${e.revision} · ${e.created_at} · ${e.reviewer_kind}:${e.reviewer} · ${e.action} · ${e.categories.join(", ")||"—"} · ${e.reason}`));
      }
      save.disabled=Boolean(state.problems.length);if(state.problems.length)message.textContent=state.problems.join(" ");
    }
    target.addEventListener("change",update);update();
    save.addEventListener("click",async()=>{
      if(!reason.value.trim()||!reviewer.value.trim()){message.textContent="Укажите причину и reviewer.";return;}
      const [target_kind,target_id]=target.value.split(":"),selected=Array.from(category.selectedOptions).map(n=>n.value);
      const body={snapshot_id:sid,target_kind,target_id,expected_revision:Number(panel.dataset.expectedRevision),action:action.value,
        categories:target_kind==="classification"&&["confirm","correct"].includes(action.value)?selected:[],reason:reason.value,
        reviewer:reviewer.value,reviewer_kind:kind.value,restore_revision:action.value==="restore"?Number(restore.value)||null:null};
      save.disabled=true;message.textContent="Сохраняется…";
      try{
        const response=await fetch(`${base}/decision`,{method:"POST",headers:{"Content-Type":"application/json","X-Terms-CSRF":review.csrf},body:JSON.stringify(body)});
        const result=await response.json();if(!response.ok)throw new Error(typeof result.detail==="string"?result.detail:JSON.stringify(result.detail));
        localStorage.setItem("ariadne-terms-reviewer",reviewer.value);remember();sessionStorage.setItem(`terms-saved:${sid}`,`Сохранено: ревизия ${result.revision}.`);location.reload();
      }catch(error){message.textContent=String(error);message.className="review-error";save.disabled=false;}
    });
  }
  document.addEventListener("ariadne:term",event=>renderForm(event.detail.article,event.detail.term));
  const saved=sessionStorage.getItem(`terms-saved:${sid}`);if(saved){status.textContent=saved;sessionStorage.removeItem(`terms-saved:${sid}`);}
  const previous=sessionStorage.getItem(storageKey);
  if(previous){
    const selected=JSON.parse(previous);if(["TAC","type","role","origin"].includes(selected.mode))host.state.mode=selected.mode;
    host.state.sort=selected.sort||"rank";host.state.kind=selected.kind;
    if(selected.term && host.data.articles.some(a=>a.terms.some(t=>t.term_id===selected.term)))host.chooseTerm(selected.term);
  }
  refreshQueue();
})();
