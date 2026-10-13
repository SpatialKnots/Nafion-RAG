import fs from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {Presentation,PresentationFile,FileBlob} from '@oai/artifact-tool';
const SKILL='C:/Users/unive/.codex/plugins/cache/openai-primary-runtime/presentations/26.905.11957/skills/presentations';
const WORK='D:/Nafion-RAG/presentations/ariadne_v1_1';
const BUILD=path.join(WORK,'build');
const OUT=path.join(WORK,'output');
process.env.RUNTIME_NODE_MODULES='C:/Users/unive/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules';
const {resolvePresentationFont,applyPresentationChartFont,finalizePresentation}=await import(pathToFileURL(path.join(SKILL,'container_tools/artifact_tool_utils.mjs')).href);
const font=resolvePresentationFont();
console.log('FONT',font);
const P=Presentation.create({slideSize:{width:1280,height:720}});
const C={ink:'#1A2E40',muted:'#5D6E7D',coral:'#D95B47',teal:'#007F87',paper:'#FFFFFF',light:'#F2F6F8'};
const SOURCE='D:/Nafion-RAG/handoffs/ARIADNE_OPTIMIZED_CONCEPT_v1_1_2026-10-06/';
function text(s,t,x,y,w,h,size=28,color=C.ink,bold=false){
const a=s.shapes.add({name:t.slice(0,36),geometry:'textbox',position:{left:x,top:y,width:w,height:h},fill:'none',line:{fill:'none',width:0}});
a.text=t;a.text.style={typeface:font,fontSize:size,color,bold,autoFit:'none'};return a;
}
function slide(title,ref,note=''){
const s=P.slides.add();s.background.fill=C.paper;
text(s,title,64,44,1152,102,44,C.ink,true);
text(s,'ARIADNE · концепция v1.1 · 06.10.2026',64,675,970,26,17,C.muted);
text(s,String(P.slides.items.length).padStart(2,'0'),1160,675,56,26,17,C.muted);
s.speakerNotes.textFrame.setText('Источник: '+SOURCE+ref+'\n'+note);
return s;
}
function statement(s,t,y=170,size=34){text(s,t,64,y,1152,110,size,C.ink,true);}
function rows(s,items,y=180,step=106){
items.forEach((a,i)=>{text(s,a[0],64,y+i*step,250,72,28,C.teal,true);text(s,a[1],350,y+i*step,850,80,28);});
}
function table(s,vals,top=172,widths=[600,536],rowHeight=62,size=26){
const t=s.tables.add({rows:vals.length,columns:vals[0].length,left:64,top,width:1152,height:rowHeight*vals.length,columnWidths:widths,values:vals});
t.borders.assign({fill:'#DDE5E9',width:1});
t.cells.block({row:0,column:0,rowCount:vals.length,columnCount:vals[0].length}).assign({textStyle:{typeface:font,fontSize:size,color:C.ink},margins:{left:12,right:12,top:7,bottom:7}});
for(let r=0;r<vals.length;r++){t.rows[r].height=rowHeight;for(let c=0;c<vals[0].length;c++){t.getCell(r,c).fill=r===0?C.ink:(r%2===0?C.light:C.paper);if(r===0){t.getCell(r,c).text.style={typeface:font,fontSize:size,color:'#FFFFFF',bold:true};}}}
return t;
}
function foot(s,t,y=616){text(s,t,64,y,1152,44,21,C.muted);}
// 1
{
const s=P.slides.add();s.background.fill=C.paper;
s.images.add({blob:new Uint8Array(await fs.readFile('D:/Nafion-RAG/app/static/brand/ariadne-logo-horizontal.png')),contentType:'image/png',alt:'Логотип ARIADNE из репозитория проекта',fit:'contain',position:{left:64,top:48,width:420,height:184}});
text(s,'Проверяемые экспериментальные\nданные из научной литературы',64,284,1152,180,52,C.ink,true);
text(s,'Локальная система для химика и исследовательской группы',64,514,1140,62,30,C.muted);
text(s,'Концепция v1.1 · 6 октября 2026 года',64,642,1100,34,22,C.muted);
s.speakerNotes.textFrame.setText('Источники: '+SOURCE+'01_PROJECT_CONCEPT.md; оригинальный логотип D:/Nafion-RAG/app/static/brand/ariadne-logo-horizontal.png. Концепция для обсуждения с ИХТТ и подготовки заявки; не поданная заявка и не готовый серийный продукт.');
}
// 2
{
const s=slide('Ошибки при сравнении материалов','01_PROJECT_CONCEPT.md');
statement(s,'Правильно распознанное число может\nотноситься к другому эксперименту',168,38);
rows(s,[['Образец','Значение связано с другой мембраной или составом.'],['Условия','Температура, влажность или среда перенесены из соседнего случая.'],['Происхождение','Расчётное значение принято за экспериментальное.']],315,94);
foot(s,'Задача ARIADNE — сохранить связи и показать подтверждающий источник.');
}
// 3
{
const s=slide('Scientific Record','04_ARCHITECTURE_AND_IP.md');
text(s,'Одна запись — одно свойство образца\nпри определённых условиях',64,168,1152,95,36,C.ink,true);
table(s,[['Что сохраняем','Как проверяем'],['Образец, свойство, величина','Явная связь в тексте или строке таблицы'],['Единица, условия, происхождение','Источник каждого извлечённого поля'],['Исходное значение и преобразование','Правило нормализации и история изменений'],['Решение химика','Подтверждение, исправление или отклонение']],282,[540,612],60,25);
foot(s,'Целевой формат. Полная связанная запись ещё не реализована и не принята научно.',604);
}
// 4
{
const s=slide('Текущий задел ARIADNE','09_CURRENT_STATE_AND_EVIDENCE.md','Сохранённый аудит 06.10.2026: pytest 595 passed, 1 warning; корпус 33 статьи, 493 страницы, 619 chunks. Retrieval 46/46 на development/regression, не независимый научный holdout. Проверки для презентации не повторялись.');
const nums=[['33','статьи в корпусе'],['595','программных тестов прошли'],['46/46','retrieval-проверок прошли']];
nums.forEach((a,i)=>{const x=64+i*385;text(s,a[0],x,177,350,120,76,C.coral,true);text(s,a[1],x,313,335,85,27,C.ink);});
text(s,'Есть ingestion/OCR, PostgreSQL, hybrid search,\nprovenance, численные кандидаты и review-задел.',64,450,1152,110,32);
foot(s,'Исторические инженерные результаты. Научное качество полной записи не доказано.');
}
// 5
{
const s=slide('Научная гипотеза и эксперимент','02_GRANT_CORE_AND_KPI.md');
statement(s,'Проверки связей должны уменьшить ошибки\nи трудоёмкость работы химика',165,35);
table(s,[['Режим','Назначение'],['B: фиксированная локальная LLM','Базовое извлечение полной записи'],['C: та же LLM + проверки','Измерение вклада checks и отказов'],['D: C + review химиком','Качество итоговой таблицы и полное время']],292,[580,572],71,26);
foot(s,'Гипотеза не проверена. Порог допуска выбирается на validation и замораживается.');
}
// 6
{
const s=slide('Границы проекта на первый год','01_PROJECT_CONCEPT.md');
table(s,[['Уровень','Содержание'],['Обязательное ядро','Один сценарий проводимости; текст и простые таблицы'],['Минимальный продукт','Review, экспорт, локальная установка и восстановление'],['После приёмки ядра','Второй домен, графики, дополнительные модели'],['Следующий этап','Серийный ARIADNE Box, роли и интеграции']],170,[365,787],88,27);
foot(s,'PFSA/Nafion — первый домен проверки. Протонный или литий-ионный сценарий ещё выбирается.',622);
}
// 7
{
const s=slide('Ограниченные проверки и решение эксперта','04_ARCHITECTURE_AND_IP.md');
text(s,'Автоматические проверки',64,171,520,62,32,C.teal,true);
text(s,'Образец ↔ значение\nУсловия ↔ конкретная запись\nЕдиница и оператор\nПроисхождение результата\nДоказательства полей',64,256,525,288,30);
text(s,'Правило допуска',672,171,540,62,32,C.teal,true);
text(s,'Недостаточно evidence\nили связь неоднозначна:\nнужна проверка химиком.',672,256,540,150,31,C.ink,true);
text(s,'Прохождение checks\nне равно подтверждению\nэкспертом.',672,443,540,135,28);
foot(s,'Универсальная проверка научной истинности в проекте не обещается.');
}
// 8
{
const s=slide('Рабочие цели качества','02_GRANT_CORE_AND_KPI.md');
table(s,[['Показатель','Цель','Что измеряем'],['Precision полной записи','≥90%','Допущенные записи до правок химика'],['Recall полной записи','≥60%','Все подходящие gold-записи'],['Provenance допущенных полей','100%','Проверяемое evidence и связи'],['Корректный отказ','≥85%','Отрицательные и неоднозначные случаи'],['Экономия времени','≥30%','Полное время проверенной таблицы']],168,[460,185,507],66,25);
foot(s,'Предложенные цели, не достигнутые показатели. Считать также coverage и ложные отказы.',588);
}
// 9
{
const s=slide('Эталон и независимая оценка','02_GRANT_CORE_AND_KPI.md');
text(s,'60 публикаций в gold',64,168,650,66,36,C.ink,true);
const chart=s.charts.add('bar',{position:{left:50,top:260,width:710,height:315},categories:['Разработка','Настройка','Test'],series:[{name:'Публикации',values:[30,15,15],fill:C.teal}],barOptions:{direction:'column',grouping:'clustered'},hasLegend:false,xAxis:{textStyle:{fontSize:25,typeface:font,fill:C.ink}},dataLabels:{showValue:true,position:'outEnd',textStyle:{fontSize:28,typeface:font,fill:C.ink,bold:true}}});
applyPresentationChartFont(chart,{fontFamily:font});
text(s,'Test не используется\nдля настройки',822,244,380,98,32,C.ink,true);
text(s,'Напарник независимо\nразмечает весь test.\nПлотность записей\nсначала измеряется\nна 10–15 статьях.',822,368,380,235,27);
foot(s,'План разметки. Рабочий корпус — около 120 публикаций; реальная трудоёмкость ещё оценивается.');
}
// 10
{
const s=slide('Первый продукт и пользователь','03_PRODUCT_AND_COMMERCIALIZATION.md');
statement(s,'Проверяемая сравнительная таблица\nдля лаборатории мембран и электролитов',167,37);
rows(s,[['Пользователь','Химик, регулярно сравнивающий свойства по публикациям.'],['Поставка года','Локальный клиент, выбранная модель, review и CSV/JSON.'],['Пилот','Реальная задача, ручной baseline и измеренный эффект.']],330,94);
foot(s,'Спрос не подтверждён: предложены 6–8 интервью и один согласованный пилот.');
}
// 11
{
const s=slide('Рабочая станция и ARIADNE Box','05_HARDWARE_AND_BUDGET.md','Исторический кандидат: две AFOX RTX3090 по24ГБ, EPYC7402P/H12SSL-I,128ГБ ECC,2ТБ TLC. CPU/RAM б/у с гарантией. Не подтверждённое предложение. ИБП, внешнее backup, монитор и подписки вне системного блока.');
text(s,'Конфигурацию определяет benchmark.\nПотолок со сборкой и доставкой — 1 млн ₽.',64,167,1152,102,36,C.ink,true);
table(s,[['Плановый предел','тыс. ₽'],['Две GPU по 24 ГБ','560'],['CPU, плата, 128 ГБ RAM и БП','285'],['SSD, корпус, охлаждение, сборка, доставка','105'],['Резерв внутри миллиона','50'],['Итого','1000']],296,[890,262],51,25);
foot(s,'Закупочные потолки. ИБП и внешнее backup отдельно. Серийный Box — после пилота.',614);
}
// 12
{
const s=slide('Дорожная карта на 12 месяцев','06_ROADMAP_AND_TEAM.md');
table(s,[['Период','Результат'],['1–2','Схема, pilot-gold, baseline, текстовый extractor'],['3–4','Связанная запись, evidence, review и экспорт'],['5–6','Простые таблицы и ограниченные checks'],['7–8','Gold, validation, backup/restore и установка'],['9–10','Пилот, время химика, заморозка конфигурации'],['11–12','Untouched test, offline-приёмка и комплект поставки']],169,[240,912],61,25);
foot(s,'Если review не экономит время — переработать ядро и снять расширения.',616);
}
// 13
{
const s=slide('Команда и реалистичный ресурс','06_ROADMAP_AND_TEAM.md');
rows(s,[['Инициатор','Химик; 20–30 ч/неделю; разработка с Codex и приёмка задач.'],['Напарник','К.х.н.; независимая разметка и научная оценка. Роль и часы согласуются.'],['Инженер','Периодическая помощь с миграциями, восстановлением и релизом.']],180,129);
text(s,'Плановая основа: 1150 часов пользователя за год,\nвключая 150 часов резерва',64,578,1152,66,28,C.teal,true);
}
// 14
{
const s=slide('Расчётный бюджет проекта','05_HARDWARE_AND_BUDGET.md','Сценарий не согласован. Зарплаты включают предполагаемые начисления; коэффициенты и организационные расходы требуют бухгалтерского расчёта. Сервисы 300тыс. не равны цене Codex Pro. Аппаратный резерв находится внутри строки станции. Свободного резерва общего проекта нет.');
table(s,[['Статья','тыс. ₽'],['Два химика с начислениями','2200'],['Станция, сборка, проверка и её резерв','1000'],['Инженерное сопровождение','600'],['Инструменты / необходимые сервисы','300'],['Независимая проверка + ИБП, backup, эксплуатация','300'],['Аналоги и права + пилот и документация','200'],['Расходы организации','400'],['Итого','5000']],163,[924,228],48,24);
s.speakerNotes.textFrame.setText('Источник: '+SOURCE+'05_HARDWARE_AND_BUDGET.md. Девять исходных статей: научный труд 2200, станция 1000, инженер 600, сервисы 300, независимая проверка 150, ИБП/backup/эксплуатация 150, аналоги/правовое сопровождение 100, пилот/документация 100, организация 400 тыс. рублей. Всего 5000. Две пары строк сгруппированы для показа. Сценарий не согласован; применимые начисления и закупка требуют проверки организации. Аппаратный резерв уже внутри станции; свободного общего резерва нет.');
text(s,'Предварительный сценарий. Смета и допустимость оборудования требуют согласования.',64,630,1152,30,21,C.muted);
}
// 15
{
const s=slide('Риски и критерии продолжения','08_DECISIONS_AND_RISKS.md');
rows(s,[['Качество','Измерять precision вместе с recall, coverage и ложными отказами.'],['Трудоёмкость','Проверять полное время; при отсутствии выигрыша менять workflow.'],['Эксплуатация','Испытать установку и восстановление; offline — с отключённой сетью.'],['Права и рынок','IP и партнёрство согласуются; интервью и продажи ещё не состоялись.']],170,106);
foot(s,'Победа в конкурсе и коммерческий успех не установлены.');
}
// 16
{
const s=slide('Предложение для обсуждения с ИХТТ','07_IHTT_ONE_PAGE_MEMO.md');
statement(s,'Согласовать короткий предзаявочный пилот',171,38);
rows(s,[['Организация','Определить руководителя, состав команды и пользователя пилота.'],['Научный сценарий','Выбрать проводимость и 10–15 публикаций для первичного опыта.'],['Ресурс и права','Уточнить смету, инфраструктуру и Background / Foreground IP.']],318,96);
foot(s,'ИХТТ — рассматриваемый партнёр. Документ для обсуждения; согласие не получено.');
}
await fs.writeFile(path.join(BUILD,'deck-content.txt'),(await P.inspect({kind:'slide,textbox,table,chart,notes',maxChars:100000})).ndjson);
await fs.writeFile(path.join(BUILD,'presentation.proto.json'),JSON.stringify(P.toProto()));
const candidate=path.join(BUILD,'candidate.pptx');
await (await PresentationFile.exportPptx(P)).save(candidate);
console.log('EXPORTED',candidate,P.slides.items.length);
for(let i=0;i<P.slides.items.length;i++){
const slide=P.slides.items[i];
const png=await P.export({slide,format:'png',scale:1});
await fs.writeFile(path.join(BUILD,'slide-'+String(i+1).padStart(2,'0')+'.png'),new Uint8Array(await png.arrayBuffer()));
}
console.log('RENDERED');
const final=path.join(OUT,'ARIADNE_Project_2026-10-06.pptx');
const result=await finalizePresentation({
workspaceDir:WORK,candidatePath:candidate,finalPath:final,
pythonExecutable:'C:/Users/unive/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe',
integrityValidatorPath:path.join(SKILL,'container_tools/inspect_presentation_package_integrity.py'),
layoutValidatorPath:path.join(SKILL,'container_tools/inspect_presentation_layout_geometry.py'),
layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-bullet-geometry','--validate-heading-fit',...[3,5,6,8,11,12,14].flatMap(n=>['--require-native-table-slide',String(n)])],
requiredNativeTableOwnerSlides:[3,5,6,8,11,12,14],
requiredNativeChartOwnerSlides:[9],
materializeLiteralChartWorkbooks:true,
explicitTotalSlideCount:16,
fontPolicy:{basis:'design',families:[font]},
verifyArtifactToolImport:true,
receiptPath:path.join(BUILD,'validation-r2.json')
});
console.log('FINAL',JSON.stringify(result));
const finalDeck=await PresentationFile.importPptx(await FileBlob.load(final));
for(let i=0;i<finalDeck.slides.items.length;i++){
const png=await finalDeck.export({slide:finalDeck.slides.items[i],format:'png',scale:1});
await fs.writeFile(path.join(BUILD,'final-'+String(i+1).padStart(2,'0')+'.png'),new Uint8Array(await png.arrayBuffer()));
}
console.log('FINAL_RENDERED',finalDeck.slides.items.length);
process.exit(0);
