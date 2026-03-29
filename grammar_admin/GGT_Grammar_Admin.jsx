import { useState, useEffect, useMemo, useCallback } from "react";
import _ from "lodash";

const C = {
  bg:"#080c10",panel:"#0d1117",card:"#121921",border:"#1c2736",
  borderLight:"#263547",text:"#c9d8e8",muted:"#5a7080",
  accent:"#e8934a",accentBg:"#1f1308",verify:"#d4a300",verifyBg:"#1a1500",
  success:"#3db86e",danger:"#e05454",blue:"#4a9ede",
  mono:"'JetBrains Mono', monospace",sans:"'Syne', sans-serif",
};

const NC_KEYS=["NC1","NC1a","NC2","NC2a","NC2b",...Array.from({length:16},(_,i)=>`NC${i+3}`)];
const CONCORD_TYPES=["subject_concords","object_concords","relative_concords","possessive_concords",
  "demonstrative_concords","adjectival_concords","adverbial_concords","relative_subject_concords",
  "relative_object_concords","enumerative_concords","independent_pronouns","quantifier_concords",
  "interrogative_concords","connective_concords","reflexive_concords","copula_concords",
  "comitative_concords","emphatic_concords"];
const TAM_KEYS=["PRES","PST","REC_PST","REM_PST","FUT_NEAR","FUT_REM","HAB","PERF"];
const EXT_KEYS=["APPL","CAUS","TRANS","CONT","RECIP","STAT","PASS","INTENS","REDUP","PERF","REV","REPET","FREQ","POS"];
const FV_KEYS=["indicative","subjunctive","negative","imperative_singular","imperative_plural","perfective","infinitive"];

function scanVerify(obj,path=[],out=[]){
  if(typeof obj==="string"&&obj.includes("# VERIFY")){out.push({path:path.join("."),value:obj});}
  else if(Array.isArray(obj)){obj.forEach((v,i)=>scanVerify(v,[...path,i],out));}
  else if(obj&&typeof obj==="object"){Object.entries(obj).forEach(([k,v])=>scanVerify(v,[...path,k],out));}
  return out;
}

const lbl$={display:"block",fontSize:10,color:C.muted,fontFamily:C.sans,letterSpacing:"0.09em",textTransform:"uppercase",marginBottom:5};
const box$={background:C.card,border:`1px solid ${C.border}`,borderRadius:8,padding:"14px 16px"};
const bHead$={fontSize:9,fontFamily:C.sans,fontWeight:800,letterSpacing:"0.18em",color:C.accent,textTransform:"uppercase",marginBottom:14};
const mIn$={background:"#09111a",border:`1px solid ${C.border}`,borderRadius:5,color:C.text,fontFamily:C.mono,fontSize:12,padding:"6px 9px",outline:"none",width:"100%",boxSizing:"border-box"};
const addB$={background:"transparent",border:`1px dashed ${C.borderLight}`,color:C.muted,cursor:"pointer",padding:"5px 12px",borderRadius:5,fontSize:11,fontFamily:C.sans};
const th$={padding:"5px 8px",textAlign:"left",fontSize:9,color:C.muted,fontFamily:C.sans,letterSpacing:"0.1em",borderBottom:`1px solid ${C.border}`,textTransform:"uppercase"};
const td$={padding:"5px 7px",borderBottom:`1px solid ${C.border}30`};

function TagEditor({values=[],onChange,placeholder="+ form"}){
  const[draft,setDraft]=useState("");
  const vals=Array.isArray(values)?values:(values?[String(values)]:[]);
  const add=()=>{const v=draft.trim();if(v){onChange([...vals,v]);setDraft("");}};
  return(
    <div style={{display:"flex",flexWrap:"wrap",gap:5,alignItems:"center"}}>
      {vals.map((v,i)=>(
        <span key={i} style={{display:"inline-flex",alignItems:"center",gap:4,background:C.accentBg,color:C.accent,fontFamily:C.mono,fontSize:12,padding:"3px 8px",borderRadius:4,border:`1px solid ${C.accent}33`}}>
          {v}<button onClick={()=>onChange(vals.filter((_,j)=>j!==i))} style={{background:"none",border:"none",color:C.accent,cursor:"pointer",padding:0,lineHeight:1,fontSize:13}}>×</button>
        </span>
      ))}
      <input value={draft} onChange={e=>setDraft(e.target.value)} onKeyDown={e=>{if(e.key==="Enter"){e.preventDefault();add();}}} placeholder={placeholder}
        style={{background:"transparent",border:`1px dashed ${C.borderLight}`,color:C.muted,fontFamily:C.mono,fontSize:11,padding:"3px 8px",borderRadius:4,outline:"none",width:80}}/>
    </div>
  );
}

function AllomorphTable({allomorphs=[],onChange}){
  const rows=Array.isArray(allomorphs)?allomorphs:[];
  const upd=(i,k,v)=>{const n=[...rows];n[i]={...n[i],[k]:v};onChange(n);};
  return(
    <div>
      {rows.length>0&&(
        <table style={{width:"100%",borderCollapse:"collapse",marginBottom:8}}>
          <thead><tr>{["Form","Condition","Cond. Formal",""].map(h=><th key={h} style={th$}>{h}</th>)}</tr></thead>
          <tbody>
            {rows.map((r,i)=>(
              <tr key={i}>
                <td style={td$}><input value={r.form||""} onChange={e=>upd(i,"form",e.target.value)} style={{...mIn$,fontSize:12}}/></td>
                <td style={td$}><input value={r.condition||""} onChange={e=>upd(i,"condition",e.target.value)} style={{...mIn$,fontSize:11}}/></td>
                <td style={td$}><input value={r.condition_formal||""} onChange={e=>upd(i,"condition_formal",e.target.value)} style={{...mIn$,fontSize:11}}/></td>
                <td style={{...td$,width:28}}><button onClick={()=>onChange(rows.filter((_,j)=>j!==i))} style={{background:"none",border:"none",color:C.danger+"88",cursor:"pointer",fontSize:14}}>✕</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <button onClick={()=>onChange([...rows,{form:"",condition:""}])} style={addB$}>+ Add allomorph</button>
    </div>
  );
}

function Field({label,value,onChange,mono=false,textarea=false,placeholder=""}){
  const s={...mIn$,fontFamily:mono?C.mono:C.sans,...(textarea?{minHeight:72,resize:"vertical"}:{})};
  return(
    <div style={{marginBottom:14}}>
      <label style={lbl$}>{label}</label>
      {textarea?<textarea value={value||""} onChange={e=>onChange(e.target.value)} style={s} placeholder={placeholder}/>
               :<input    value={value||""} onChange={e=>onChange(e.target.value)} style={s} placeholder={placeholder}/>}
    </div>
  );
}

function SectionHeader({title,subtitle,right}){
  return(
    <div style={{marginBottom:24,paddingBottom:14,borderBottom:`1px solid ${C.border}`,display:"flex",alignItems:"flex-start",justifyContent:"space-between"}}>
      <div>
        <h2 style={{margin:0,color:C.text,fontFamily:C.sans,fontWeight:800,fontSize:17}}>{title}</h2>
        {subtitle&&<p style={{margin:"4px 0 0",color:C.muted,fontSize:11,fontFamily:C.sans}}>{subtitle}</p>}
      </div>
      {right}
    </div>
  );
}

function MetadataEditor({grammar,upd}){
  const lang=grammar?.metadata?.language;
  if(!lang)return <div style={{color:C.muted}}>No metadata.</div>;
  const b="metadata.language";
  return(
    <div>
      <SectionHeader title="Language Metadata" subtitle="Core language identification and bibliographic data"/>
      <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:20}}>
        <div style={box$}>
          <div style={bHead$}>Identification</div>
          {[["Language Name",`${b}.name`,true],["ISO 639-3",`${b}.iso_code`,true],
            ["Guthrie Code",`${b}.guthrie`,true],["Primary Region",`${b}.primary_region`,false],
            ["Approx. Speakers",`${b}.approximate_speakers`,true],["Family",`${b}.family`,false],
          ].map(([l,p,m])=><Field key={p} label={l} value={_.get(grammar,p)||""} onChange={v=>upd(p,v)} mono={m}/>)}
        </div>
        <div>
          <div style={{...box$,marginBottom:16}}>
            <div style={bHead$}>Dialects</div>
            <TagEditor values={lang.dialects||[]} onChange={v=>upd(`${b}.dialects`,v)} placeholder="+ dialect"/>
          </div>
          <div style={box$}>
            <div style={bHead$}>Reference</div>
            <Field label="Reference Grammar" value={grammar?.metadata?.reference_grammar||""} onChange={v=>upd("metadata.reference_grammar",v)}/>
            <Field label="Version" value={grammar?.metadata?.version||""} onChange={v=>upd("metadata.version",v)} mono/>
          </div>
        </div>
        <div style={{...box$,gridColumn:"1/-1"}}>
          <div style={bHead$}>Description</div>
          <Field label="" value={lang.description||""} onChange={v=>upd(`${b}.description`,v)} textarea/>
        </div>
      </div>
    </div>
  );
}

function NounClassEditor({grammar,upd,selectedNC,setSelectedNC}){
  const ncs=grammar?.noun_class_system?.noun_classes;
  if(!ncs)return <div style={{color:C.muted}}>No noun class data.</div>;
  const nc=ncs[selectedNC];
  const b=`noun_class_system.noun_classes.${selectedNC}`;
  return(
    <div>
      <SectionHeader title="Noun Classes" subtitle="Prefix forms, allomorphs, augment, semantics, and class metadata"/>
      <div style={{display:"flex",flexWrap:"wrap",gap:6,marginBottom:24}}>
        {NC_KEYS.filter(k=>ncs[k]).map(k=>(
          <button key={k} onClick={()=>setSelectedNC(k)} style={{padding:"4px 11px",borderRadius:20,fontSize:11,cursor:"pointer",fontFamily:C.mono,fontWeight:700,background:selectedNC===k?C.accent:C.card,color:selectedNC===k?"#fff":C.muted,border:`1px solid ${selectedNC===k?C.accent:C.border}`,transition:"all 0.12s"}}>{k}</button>
        ))}
      </div>
      {!nc?<div style={{color:C.muted}}>Class not found.</div>:(
        <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:20}}>
          <div style={{display:"flex",flexDirection:"column",gap:16}}>
            <div style={box$}>
              <div style={bHead$}>Prefix</div>
              <div style={{marginBottom:14}}>
                <label style={lbl$}>Canonical Form</label>
                <input value={nc.prefix?.canonical_form||""} onChange={e=>upd(`${b}.prefix.canonical_form`,e.target.value)} style={{...mIn$,fontSize:16,padding:"8px 12px"}}/>
              </div>
              <div style={{display:"grid",gridTemplateColumns:"80px 1fr",gap:12,marginBottom:14}}>
                <div>
                  <label style={lbl$}>Tone</label>
                  <select value={nc.prefix?.tone||"L"} onChange={e=>upd(`${b}.prefix.tone`,e.target.value)} style={{...mIn$,cursor:"pointer"}}>
                    {["L","H","L-H","H-L","L-L","H-H"].map(t=><option key={t} value={t}>{t}</option>)}
                  </select>
                </div>
                <div>
                  <label style={lbl$}>Frequency</label>
                  <select value={nc.frequency||"medium"} onChange={e=>upd(`${b}.frequency`,e.target.value)} style={{...mIn$,cursor:"pointer",fontFamily:C.sans}}>
                    {["very_high","high","medium","low","limited"].map(f=><option key={f} value={f}>{f}</option>)}
                  </select>
                </div>
              </div>
              <div>
                <label style={lbl$}>Notes / Verify flags</label>
                <textarea value={nc.prefix?.notes||""} onChange={e=>upd(`${b}.prefix.notes`,e.target.value)}
                  style={{...mIn$,minHeight:68,resize:"vertical",fontSize:11,borderColor:(nc.prefix?.notes||"").includes("VERIFY")?C.verify+"77":C.border}}/>
              </div>
            </div>
            <div style={box$}>
              <div style={bHead$}>Augment</div>
              <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:12}}>
                <div>
                  <label style={lbl$}>Form</label>
                  <input value={nc.augment?.form||""} onChange={e=>upd(`${b}.augment.form`,e.target.value||null)} style={mIn$} placeholder="null = none"/>
                </div>
                <div>
                  <label style={lbl$}>Usage</label>
                  <select value={nc.augment?.usage||"not_applicable"} onChange={e=>upd(`${b}.augment.usage`,e.target.value)} style={{...mIn$,cursor:"pointer",fontFamily:C.sans}}>
                    {["optional","obligatory","not_applicable","rare"].map(u=><option key={u} value={u}>{u}</option>)}
                  </select>
                </div>
              </div>
            </div>
            <div style={box$}>
              <div style={bHead$}>Classification</div>
              <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:12}}>
                <div>
                  <label style={lbl$}>Class Type</label>
                  <select value={nc.class_type||"regular"} onChange={e=>upd(`${b}.class_type`,e.target.value)} style={{...mIn$,cursor:"pointer",fontFamily:C.sans,fontSize:12}}>
                    {["regular","irregular","subclass","verbal","locative"].map(t=><option key={t} value={t}>{t}</option>)}
                  </select>
                </div>
                <div>
                  <label style={lbl$}>Paired Class</label>
                  <input value={nc.paired_class||""} onChange={e=>upd(`${b}.paired_class`,e.target.value||null)} style={mIn$} placeholder="e.g. NC2"/>
                </div>
                <div>
                  <label style={lbl$}>Gram. Number</label>
                  <select value={nc.grammatical_number||"singular"} onChange={e=>upd(`${b}.grammatical_number`,e.target.value)} style={{...mIn$,cursor:"pointer",fontFamily:C.sans,fontSize:12}}>
                    {["singular","plural","null"].map(n=><option key={n} value={n}>{n}</option>)}
                  </select>
                </div>
                <div style={{display:"flex",alignItems:"center",gap:8,paddingTop:18}}>
                  <input type="checkbox" checked={nc.active!==false} onChange={e=>upd(`${b}.active`,e.target.checked)} style={{accentColor:C.accent,width:14,height:14}}/>
                  <span style={{fontSize:12,color:C.text,fontFamily:C.sans}}>Active class</span>
                </div>
              </div>
            </div>
          </div>
          <div style={{display:"flex",flexDirection:"column",gap:16}}>
            <div style={box$}>
              <div style={bHead$}>Allomorphs</div>
              <AllomorphTable allomorphs={nc.prefix?.allomorphs||[]} onChange={v=>upd(`${b}.prefix.allomorphs`,v)}/>
            </div>
            <div style={box$}>
              <div style={bHead$}>Semantics</div>
              <Field label="Primary Domain" value={nc.semantics?.primary_domain||""} onChange={v=>upd(`${b}.semantics.primary_domain`,v)} mono/>
              <div style={{marginBottom:14}}>
                <label style={lbl$}>Features</label>
                <TagEditor values={nc.semantics?.features||[]} onChange={v=>upd(`${b}.semantics.features`,v)} placeholder="+ feature"/>
              </div>
              <div>
                <label style={lbl$}>Typical Referents</label>
                <TagEditor values={nc.semantics?.typical_referents||[]} onChange={v=>upd(`${b}.semantics.typical_referents`,v)} placeholder="+ referent"/>
              </div>
            </div>
            <div style={box$}>
              <div style={bHead$}>Triggered Rules</div>
              <TagEditor values={nc.triggers_rules||[]} onChange={v=>upd(`${b}.triggers_rules`,v)} placeholder="+ rule ID"/>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function ConcordEditor({grammar,upd,selectedConcord,setSelectedConcord}){
  const concords=grammar?.concord_system?.concords;
  const[subGroup,setSubGroup]=useState("proximal");
  if(!concords)return <div style={{color:C.muted}}>No concord data.</div>;
  const concordData=concords[selectedConcord];
  const base=`concord_system.concords.${selectedConcord}`;
  const subGroupKeys=concordData?Object.keys(concordData).filter(k=>{
    const v=concordData[k];return v&&typeof v==="object"&&!Array.isArray(v)&&!("forms"in v)&&k!=="description";
  }):[];
  const isSubGrouped=subGroupKeys.length>0;
  const workingData=isSubGrouped?(concordData[subGroup]||{}):concordData||{};
  const workingBase=isSubGrouped?`${base}.${subGroup}`:base;
  const entryKeys=Object.keys(workingData).filter(k=>{const v=workingData[k];return v&&typeof v==="object"&&!Array.isArray(v)&&"forms"in v;});
  return(
    <div>
      <SectionHeader title="Concord Paradigms" subtitle="Agreement forms for each noun class across all 18 concord types"/>
      <div style={{display:"flex",flexWrap:"wrap",gap:5,marginBottom:20}}>
        {CONCORD_TYPES.map(ct=>(
          <button key={ct} onClick={()=>setSelectedConcord(ct)} style={{padding:"3px 9px",borderRadius:4,fontSize:10,cursor:"pointer",fontFamily:C.sans,whiteSpace:"nowrap",background:selectedConcord===ct?C.accent+"22":"transparent",color:selectedConcord===ct?C.accent:C.muted,border:`1px solid ${selectedConcord===ct?C.accent:C.border}`,fontWeight:selectedConcord===ct?700:400}}>
            {ct.replace(/_/g," ").replace("concords","").trim()||ct}
          </button>
        ))}
      </div>
      {isSubGrouped&&(
        <div style={{display:"flex",gap:4,marginBottom:16}}>
          {subGroupKeys.map(sg=>(
            <button key={sg} onClick={()=>setSubGroup(sg)} style={{padding:"5px 14px",borderRadius:5,fontSize:11,cursor:"pointer",fontFamily:C.sans,fontWeight:700,background:subGroup===sg?C.blue+"22":C.card,color:subGroup===sg?C.blue:C.muted,border:`1px solid ${subGroup===sg?C.blue:C.border}`}}>{sg}</button>
          ))}
        </div>
      )}
      {entryKeys.length>0?(
        <div style={{overflowX:"auto"}}>
          <table style={{width:"100%",borderCollapse:"collapse"}}>
            <thead><tr>
              <th style={{...th$,width:80}}>KEY</th>
              <th style={{...th$,minWidth:180}}>FORMS</th>
              <th style={{...th$,width:80}}>TONE</th>
              <th style={{...th$,minWidth:120}}>GLOSS</th>
              <th style={th$}>NOTE</th>
            </tr></thead>
            <tbody>
              {entryKeys.map(k=>{
                const e=workingData[k];
                return(
                  <tr key={k} style={{borderBottom:`1px solid ${C.border}20`}}>
                    <td style={{...td$,verticalAlign:"middle"}}><span style={{fontFamily:C.mono,fontSize:12,color:k.startsWith("NC")?C.accent:C.blue,fontWeight:700}}>{k}</span></td>
                    <td style={{...td$,verticalAlign:"middle"}}><TagEditor values={Array.isArray(e.forms)?e.forms:(e.forms?[String(e.forms)]:[])} onChange={v=>upd(`${workingBase}.${k}.forms`,v)}/></td>
                    <td style={{...td$,verticalAlign:"middle"}}>
                      <select value={e.tone||"L"} onChange={ev=>upd(`${workingBase}.${k}.tone`,ev.target.value)} style={{...mIn$,width:70,padding:"4px 5px",fontSize:11,cursor:"pointer"}}>
                        {["L","H","L-L","L-H","H-L","H-H","L-H-L","varies"].map(t=><option key={t} value={t}>{t}</option>)}
                      </select>
                    </td>
                    <td style={{...td$,verticalAlign:"middle"}}><input value={e.gloss||""} onChange={ev=>upd(`${workingBase}.${k}.gloss`,ev.target.value)} style={{...mIn$,fontSize:11}}/></td>
                    <td style={{...td$,verticalAlign:"middle"}}><input value={e.note||""} onChange={ev=>upd(`${workingBase}.${k}.note`,ev.target.value)} style={{...mIn$,fontSize:11,borderColor:(e.note||"").includes("VERIFY")?C.verify+"88":C.border}} placeholder="note / # VERIFY..."/></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ):<div style={{color:C.muted,padding:32,textAlign:"center",fontSize:12}}>No entries found{isSubGrouped?` / ${subGroup}`:""}</div>}
    </div>
  );
}

function VerbSystemEditor({grammar,upd}){
  const[subTab,setSubTab]=useState("tam");
  const[selExt,setSelExt]=useState("APPL");
  const vsc=grammar?.verb_system?.verbal_system_components;
  if(!vsc)return <div style={{color:C.muted}}>No verb system data.</div>;
  const tam=vsc.tam||{};const exts=vsc.derivational_extensions||{};
  const fvs=vsc.final_vowels||{};const negPre=vsc.negation_pre||{};
  const negInfix=vsc.negation_infix||{};
  const bT="verb_system.verbal_system_components.tam";
  const bE="verb_system.verbal_system_components.derivational_extensions";
  const bF="verb_system.verbal_system_components.final_vowels";
  const bN="verb_system.verbal_system_components.negation_pre";
  const bNI="verb_system.verbal_system_components.negation_infix";
  return(
    <div>
      <SectionHeader title="Verb System" subtitle="TAM markers, extensions, final vowels, and negation"/>
      <div style={{display:"flex",gap:4,marginBottom:22}}>
        {[{id:"tam",l:"TAM Markers"},{id:"ext",l:"Extensions"},{id:"fv",l:"Final Vowels"},{id:"neg",l:"Negation"}].map(st=>(
          <button key={st.id} onClick={()=>setSubTab(st.id)} style={{padding:"6px 16px",borderRadius:6,fontSize:12,cursor:"pointer",fontFamily:C.sans,fontWeight:700,background:subTab===st.id?C.accent+"22":"transparent",color:subTab===st.id?C.accent:C.muted,border:`1px solid ${subTab===st.id?C.accent:C.border}`}}>{st.l}</button>
        ))}
      </div>
      {subTab==="tam"&&(
        <div style={{display:"flex",flexDirection:"column",gap:10}}>
          {TAM_KEYS.filter(k=>tam[k]).map(k=>(
            <div key={k} style={box$}>
              <div style={{display:"flex",alignItems:"center",gap:10,marginBottom:12}}>
                <span style={{...bHead$,marginBottom:0}}>{k}</span>
                <span style={{fontFamily:C.mono,fontSize:11,color:C.muted}}>{tam[k]?.gloss||""}</span>
              </div>
              <div style={{display:"grid",gridTemplateColumns:"1fr 80px 80px 1fr",gap:10}}>
                <div>
                  <label style={lbl$}>Forms</label>
                  <input value={Array.isArray(tam[k]?.forms)?tam[k].forms.join(", "):(tam[k]?.forms||"")}
                    onChange={e=>{const v=e.target.value;upd(`${bT}.${k}.forms`,v.includes(",")?v.split(",").map(s=>s.trim()).filter(Boolean):v);}}
                    style={mIn$} placeholder="a or a, b"/>
                </div>
                <div><label style={lbl$}>Tone</label><input value={tam[k]?.tone||""} onChange={e=>upd(`${bT}.${k}.tone`,e.target.value)} style={mIn$}/></div>
                <div><label style={lbl$}>Gloss</label><input value={tam[k]?.gloss||""} onChange={e=>upd(`${bT}.${k}.gloss`,e.target.value)} style={mIn$}/></div>
                <div><label style={lbl$}>Function</label><input value={tam[k]?.function||""} onChange={e=>upd(`${bT}.${k}.function`,e.target.value)} style={mIn$}/></div>
              </div>
              <div style={{marginTop:10}}>
                <label style={lbl$}>Note</label>
                <textarea value={tam[k]?.note||""} onChange={e=>upd(`${bT}.${k}.note`,e.target.value)}
                  style={{...mIn$,minHeight:48,resize:"vertical",fontSize:11,borderColor:(tam[k]?.note||"").includes("VERIFY")?C.verify+"77":C.border}}/>
              </div>
            </div>
          ))}
        </div>
      )}
      {subTab==="ext"&&(
        <div style={{display:"grid",gridTemplateColumns:"155px 1fr",gap:20}}>
          <div style={{display:"flex",flexDirection:"column",gap:3}}>
            {EXT_KEYS.filter(k=>exts[k]).map(k=>(
              <button key={k} onClick={()=>setSelExt(k)} style={{padding:"7px 12px",borderRadius:6,textAlign:"left",cursor:"pointer",background:selExt===k?C.accent+"18":C.card,border:`1px solid ${selExt===k?C.accent:C.border}`,color:selExt===k?C.accent:C.text,fontFamily:C.mono,fontSize:12}}>
                <span style={{fontWeight:700}}>{k}</span>
                <span style={{color:C.muted,fontSize:9,display:"block",marginTop:1}}>{exts[k]?.zone||""}</span>
              </button>
            ))}
          </div>
          {exts[selExt]&&(
            <div style={{display:"flex",flexDirection:"column",gap:14}}>
              <div style={box$}>
                <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:14}}>
                  <span style={bHead$}>{selExt}</span>
                  <span style={{padding:"2px 8px",borderRadius:4,fontSize:10,fontFamily:C.mono,background:C.accentBg,color:C.accent,border:`1px solid ${C.accent}33`}}>{exts[selExt]?.zone||""}</span>
                </div>
                <div style={{marginBottom:14}}>
                  <label style={lbl$}>Forms</label>
                  <TagEditor values={Array.isArray(exts[selExt]?.form)?exts[selExt].form:(exts[selExt]?.form?[exts[selExt].form]:[])} onChange={v=>upd(`${bE}.${selExt}.form`,v)}/>
                </div>
                <Field label="Function" value={exts[selExt]?.function||""} onChange={v=>upd(`${bE}.${selExt}.function`,v)}/>
                <Field label="Gloss" value={exts[selExt]?.gloss||""} onChange={v=>upd(`${bE}.${selExt}.gloss`,v)} mono/>
              </div>
              <div style={box$}>
                <div style={bHead$}>Allomorphs</div>
                <AllomorphTable allomorphs={exts[selExt]?.allomorphs||[]} onChange={v=>upd(`${bE}.${selExt}.allomorphs`,v)}/>
              </div>
              <div style={box$}>
                <div style={bHead$}>Notes</div>
                <textarea value={exts[selExt]?.notes||""} onChange={e=>upd(`${bE}.${selExt}.notes`,e.target.value)}
                  style={{...mIn$,minHeight:80,resize:"vertical",fontSize:11,borderColor:(exts[selExt]?.notes||"").includes("VERIFY")?C.verify+"77":C.border}}/>
              </div>
            </div>
          )}
        </div>
      )}
      {subTab==="fv"&&(
        <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:14}}>
          {FV_KEYS.filter(k=>fvs[k]).map(k=>(
            <div key={k} style={box$}>
              <div style={bHead$}>{k.replace(/_/g," ")}</div>
              <div style={{display:"grid",gridTemplateColumns:"60px 1fr",gap:10,marginBottom:10}}>
                <div><label style={lbl$}>Form</label><input value={fvs[k]?.forms||""} onChange={e=>upd(`${bF}.${k}.forms`,e.target.value)} style={mIn$}/></div>
                <div><label style={lbl$}>Function</label><input value={fvs[k]?.function||""} onChange={e=>upd(`${bF}.${k}.function`,e.target.value)} style={mIn$}/></div>
              </div>
              <div>
                <label style={lbl$}>Note</label>
                <textarea value={fvs[k]?.note||""} onChange={e=>upd(`${bF}.${k}.note`,e.target.value)}
                  style={{...mIn$,minHeight:46,resize:"vertical",fontSize:11,borderColor:(fvs[k]?.note||"").includes("VERIFY")?C.verify+"77":C.border}}/>
              </div>
            </div>
          ))}
        </div>
      )}
      {subTab==="neg"&&(
        <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:14}}>
          {Object.keys(negPre).map(k=>(
            <div key={k} style={box$}>
              <div style={bHead$}>{k} (pre-initial)</div>
              <div style={{marginBottom:12}}>
                <label style={lbl$}>Forms</label>
                <TagEditor values={Array.isArray(negPre[k]?.forms)?negPre[k].forms:(negPre[k]?.forms?[negPre[k].forms]:[])} onChange={v=>upd(`${bN}.${k}.forms`,v.length===1?v[0]:v)}/>
              </div>
              <Field label="Usage Context" value={negPre[k]?.usage_context||""} onChange={v=>upd(`${bN}.${k}.usage_context`,v)}/>
              <Field label="Note" value={negPre[k]?.note||""} onChange={v=>upd(`${bN}.${k}.note`,v)} textarea/>
            </div>
          ))}
          {negInfix?.negative&&(
            <div style={box$}>
              <div style={bHead$}>Negation Infix</div>
              <div style={{marginBottom:12}}><label style={lbl$}>Forms</label><input value={negInfix.negative?.forms||""} onChange={e=>upd(`${bNI}.negative.forms`,e.target.value)} style={mIn$}/></div>
              <Field label="Function" value={negInfix.negative?.function||""} onChange={v=>upd(`${bNI}.negative.function`,v)}/>
              <Field label="Note" value={negInfix.negative?.note||""} onChange={v=>upd(`${bNI}.negative.note`,v)} textarea/>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function VerifyManager({grammar,upd}){
  const items=useMemo(()=>scanVerify(grammar||{}),[grammar]);
  const[search,setSearch]=useState("");
  const[editing,setEditing]=useState(null);
  const[drafts,setDrafts]=useState({});
  const filtered=search?items.filter(it=>it.path.toLowerCase().includes(search.toLowerCase())||it.value.toLowerCase().includes(search.toLowerCase())):items;
  const startEdit=item=>{setEditing(item.path);setDrafts(p=>({...p,[item.path]:item.value}));};
  const save=item=>{upd(item.path,drafts[item.path]);setEditing(null);};
  const resolve=item=>{const c=item.value.replace(/\s*#\s*VERIFY[^"'\n]*/g,"").trim();upd(item.path,c||null);};
  return(
    <div>
      <SectionHeader title="VERIFY Flags" subtitle={`${items.length} flag${items.length!==1?"s":""} across all sections`}
        right={<span style={{fontFamily:C.mono,fontSize:13,fontWeight:700,color:items.length>0?C.verify:C.success}}>{items.length>0?`⚑ ${items.length}`:"✓ All clear"}</span>}/>
      {items.length===0?(
        <div style={{textAlign:"center",padding:56}}>
          <div style={{fontSize:40,marginBottom:12}}>✓</div>
          <div style={{fontFamily:C.sans,fontSize:14,color:C.success}}>No VERIFY flags remaining</div>
        </div>
      ):(
        <>
          <div style={{marginBottom:16}}><input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Filter by path or text…" style={{...mIn$,maxWidth:420}}/></div>
          <div style={{display:"flex",flexDirection:"column",gap:8}}>
            {filtered.map((item,idx)=>(
              <div key={idx} style={{...box$,borderLeft:`3px solid ${C.verify}`,paddingLeft:14}}>
                <div style={{fontFamily:C.mono,fontSize:9,color:C.muted,marginBottom:6,wordBreak:"break-all"}}>{item.path}</div>
                {editing===item.path?(
                  <textarea value={drafts[item.path]||""} onChange={e=>setDrafts(p=>({...p,[item.path]:e.target.value}))} autoFocus
                    style={{...mIn$,minHeight:60,fontSize:11,resize:"vertical",width:"100%",marginBottom:8,boxSizing:"border-box"}}/>
                ):(
                  <div style={{fontFamily:C.mono,fontSize:11,color:C.verify,background:C.verifyBg,padding:"7px 10px",borderRadius:4,lineHeight:1.6,marginBottom:8}}>{item.value}</div>
                )}
                <div style={{display:"flex",gap:6}}>
                  {editing===item.path?(
                    <>
                      <button onClick={()=>save(item)} style={{padding:"4px 12px",borderRadius:4,fontSize:11,cursor:"pointer",background:C.success+"22",color:C.success,border:`1px solid ${C.success}44`,fontFamily:C.sans,fontWeight:700}}>Save</button>
                      <button onClick={()=>setEditing(null)} style={{padding:"4px 12px",borderRadius:4,fontSize:11,cursor:"pointer",background:"transparent",color:C.muted,border:`1px solid ${C.border}`,fontFamily:C.sans}}>Cancel</button>
                    </>
                  ):(
                    <>
                      <button onClick={()=>startEdit(item)} style={{padding:"4px 12px",borderRadius:4,fontSize:11,cursor:"pointer",background:C.accentBg,color:C.accent,border:`1px solid ${C.accent}44`,fontFamily:C.sans,fontWeight:700}}>Edit</button>
                      <button onClick={()=>resolve(item)} style={{padding:"4px 12px",borderRadius:4,fontSize:11,cursor:"pointer",background:C.success+"18",color:C.success,border:`1px solid ${C.success}33`,fontFamily:C.sans,fontWeight:700}} title="Strip # VERIFY text">✓ Resolve</button>
                    </>
                  )}
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

export default function GrammarAdmin(){
  const[yamlLoaded,setYamlLoaded]=useState(false);
  const[grammar,setGrammar]=useState(null);
  const[fileName,setFileName]=useState("");
  const[tab,setTab]=useState("nc");
  const[selNC,setSelNC]=useState("NC1");
  const[selConc,setSelConc]=useState("subject_concords");
  const[toast,setToast]=useState(null);
  const[modified,setModified]=useState(false);
  const[drag,setDrag]=useState(false);

  useEffect(()=>{
    const s=document.createElement("script");
    s.src="https://cdnjs.cloudflare.com/ajax/libs/js-yaml/4.1.0/js-yaml.min.js";
    s.onload=()=>setYamlLoaded(true);document.head.appendChild(s);
    const l=document.createElement("link");
    l.rel="stylesheet";l.href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Syne:wght@400;600;700;800&display=swap";
    document.head.appendChild(l);
  },[]);

  useEffect(()=>{
    if(!grammar)return;
    try{window.storage?.set("ggt_g",JSON.stringify(grammar));window.storage?.set("ggt_f",fileName);}catch{}
  },[grammar,fileName]);

  useEffect(()=>{
    (async()=>{try{const g=await window.storage?.get("ggt_g");const f=await window.storage?.get("ggt_f");if(g?.value){setGrammar(JSON.parse(g.value));setFileName(f?.value||"grammar.yaml");}}catch{}})();
  },[]);

  const toast$=(msg,type="ok")=>{setToast({msg,type});setTimeout(()=>setToast(null),2800);};

  const parseFile=(text,name)=>{
    if(!window.jsyaml){toast$("Parser loading…","err");return;}
    try{setGrammar(window.jsyaml.load(text));setFileName(name);setModified(false);toast$(`Loaded ${name}`);}
    catch(e){toast$("Parse error: "+e.message.slice(0,55),"err");}
  };

  const handleFile=f=>{if(!f)return;const r=new FileReader();r.onload=e=>parseFile(e.target.result,f.name);r.readAsText(f);};

  const handleDownload=()=>{
    if(!grammar||!window.jsyaml)return;
    try{const y=window.jsyaml.dump(grammar,{indent:2,lineWidth:-1,noRefs:true});const b=new Blob([y],{type:"text/yaml"});const a=document.createElement("a");a.href=URL.createObjectURL(b);a.download=fileName||"grammar.yaml";a.click();setModified(false);toast$("Downloaded!");}
    catch{toast$("Export error","err");}
  };

  const upd=useCallback((path,val)=>{setGrammar(prev=>{const n=_.cloneDeep(prev);_.set(n,path,val);return n;});setModified(true);},[]);

  const langName=grammar?.metadata?.language?.name||"—";
  const vCount=useMemo(()=>grammar?scanVerify(grammar).length:0,[grammar]);

  const TABS=[
    {id:"meta",icon:"◎",label:"Metadata"},
    {id:"nc",icon:"N",label:"Noun Classes"},
    {id:"concords",icon:"C",label:"Concords"},
    {id:"verb",icon:"V",label:"Verb System"},
    {id:"verify",icon:"!",label:`VERIFY ${vCount>0?`(${vCount})`:""}`,warn:vCount>0},
  ];

  if(!grammar)return(
    <div style={{minHeight:"100vh",background:C.bg,display:"flex",alignItems:"center",justifyContent:"center",fontFamily:C.sans}}
      onDragOver={e=>{e.preventDefault();setDrag(true);}} onDragLeave={()=>setDrag(false)}
      onDrop={e=>{e.preventDefault();setDrag(false);handleFile(e.dataTransfer.files[0]);}}>
      <div style={{textAlign:"center",padding:"48px 56px",border:`2px dashed ${drag?C.accent:C.border}`,borderRadius:16,maxWidth:460,background:drag?C.accentBg:"transparent",transition:"all 0.2s"}}>
        <div style={{fontSize:52,marginBottom:18}}>⌘</div>
        <h1 style={{color:C.text,fontWeight:800,fontSize:22,margin:"0 0 6px",fontFamily:C.sans,letterSpacing:"-0.02em"}}>GGT Grammar Admin</h1>
        <p style={{color:C.muted,fontSize:12,margin:"0 0 10px",fontFamily:C.sans,letterSpacing:"0.04em",textTransform:"uppercase"}}>Gobelo Grammar Toolkit</p>
        <p style={{color:C.muted,fontSize:13,margin:"0 0 32px",lineHeight:1.7}}>
          Drop a <code style={{color:C.accent,fontFamily:C.mono}}>.yaml</code> grammar file or click to upload.<br/>Edits auto-saved to browser storage.
        </p>
        <label style={{display:"inline-block",padding:"12px 30px",borderRadius:8,background:C.accent,color:"#fff",fontWeight:800,fontSize:13,cursor:"pointer",letterSpacing:"0.06em",fontFamily:C.sans,boxShadow:`0 4px 24px ${C.accent}44`}}>
          Upload YAML<input type="file" accept=".yaml,.yml" onChange={e=>handleFile(e.target.files[0])} style={{display:"none"}}/>
        </label>
        {!yamlLoaded&&<p style={{color:C.muted,fontSize:10,marginTop:20,fontFamily:C.mono}}>Loading YAML parser…</p>}
      </div>
    </div>
  );

  return(
    <div style={{minHeight:"100vh",background:C.bg,display:"flex",flexDirection:"column",fontFamily:C.sans,color:C.text}}>
      <div style={{display:"flex",alignItems:"center",gap:14,padding:"0 20px",height:50,background:C.panel,borderBottom:`1px solid ${C.border}`,flexShrink:0,position:"sticky",top:0,zIndex:10}}>
        <span style={{fontWeight:800,fontSize:13,color:C.accent,letterSpacing:"0.1em",fontFamily:C.sans}}>GGT ADMIN</span>
        <div style={{width:1,height:18,background:C.border}}/>
        <span style={{fontSize:12,color:C.text,fontFamily:C.mono}}>{fileName}</span>
        <span style={{fontSize:11,color:C.muted,fontFamily:C.mono}}>[{langName}]</span>
        {modified&&<span style={{fontSize:10,color:C.verify,fontWeight:700,fontFamily:C.sans}}>● unsaved</span>}
        <div style={{flex:1}}/>
        <label style={{padding:"5px 13px",borderRadius:5,background:C.card,border:`1px solid ${C.border}`,color:C.muted,cursor:"pointer",fontSize:11,fontWeight:700,fontFamily:C.sans,letterSpacing:"0.04em"}}>
          Load File<input type="file" accept=".yaml,.yml" onChange={e=>handleFile(e.target.files[0])} style={{display:"none"}}/>
        </label>
        <button onClick={handleDownload} style={{padding:"5px 18px",borderRadius:5,background:C.accent,color:"#fff",border:"none",cursor:"pointer",fontSize:11,fontWeight:800,letterSpacing:"0.06em",fontFamily:C.sans,boxShadow:`0 2px 12px ${C.accent}44`}}>↓ Download YAML</button>
      </div>
      <div style={{display:"flex",flex:1,overflow:"hidden"}}>
        <div style={{width:172,background:C.panel,borderRight:`1px solid ${C.border}`,padding:"14px 0",flexShrink:0,display:"flex",flexDirection:"column"}}>
          {TABS.map(t=>(
            <button key={t.id} onClick={()=>setTab(t.id)} style={{display:"flex",alignItems:"center",gap:10,padding:"10px 16px",border:"none",background:"none",cursor:"pointer",textAlign:"left",color:tab===t.id?C.accent:C.muted,fontFamily:C.sans,fontSize:13,fontWeight:tab===t.id?700:400,borderRight:`2px solid ${tab===t.id?C.accent:"transparent"}`,transition:"all 0.1s"}}>
              <span style={{fontFamily:C.mono,fontSize:10,fontWeight:700,width:14,color:t.warn?C.verify:(tab===t.id?C.accent:C.borderLight)}}>{t.icon}</span>
              {t.label}
            </button>
          ))}
          <div style={{marginTop:"auto",padding:"14px 16px",borderTop:`1px solid ${C.border}`}}>
            <div style={{fontSize:9,color:C.muted,letterSpacing:"0.1em",marginBottom:6,textTransform:"uppercase",fontFamily:C.sans}}>Stats</div>
            {[["NC Classes",Object.keys(grammar?.noun_class_system?.noun_classes||{}).length],["Concord Types",Object.keys(grammar?.concord_system?.concords||{}).length],["VERIFY flags",vCount]].map(([l,v])=>(
              <div key={l} style={{display:"flex",justifyContent:"space-between",fontSize:11,marginBottom:3}}>
                <span style={{color:C.muted,fontFamily:C.sans}}>{l}</span>
                <span style={{fontFamily:C.mono,color:(l.includes("VERIFY")&&v>0)?C.verify:C.text}}>{v}</span>
              </div>
            ))}
          </div>
        </div>
        <div style={{flex:1,overflowY:"auto",padding:26,background:C.bg}}>
          {tab==="meta"&&<MetadataEditor grammar={grammar} upd={upd}/>}
          {tab==="nc"&&<NounClassEditor grammar={grammar} upd={upd} selectedNC={selNC} setSelectedNC={setSelNC}/>}
          {tab==="concords"&&<ConcordEditor grammar={grammar} upd={upd} selectedConcord={selConc} setSelectedConcord={setSelConc}/>}
          {tab==="verb"&&<VerbSystemEditor grammar={grammar} upd={upd}/>}
          {tab==="verify"&&<VerifyManager grammar={grammar} upd={upd}/>}
        </div>
      </div>
      {toast&&<div style={{position:"fixed",bottom:22,right:22,zIndex:999,padding:"10px 18px",borderRadius:8,fontFamily:C.sans,fontSize:12,background:toast.type==="err"?C.danger:C.success,color:"#fff",fontWeight:700,boxShadow:"0 4px 24px rgba(0,0,0,0.5)"}}>{toast.msg}</div>}
    </div>
  );
}
