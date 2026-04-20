
import { useState, useEffect, useRef, useCallback } from "react";

// ─── Google Fonts ─────────────────────────────────────────────────────────────
const fontLink = document.createElement("link");
fontLink.rel = "stylesheet";
fontLink.href = "https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Sans:wght@300;400;500;600&family=DM+Mono:wght@400;500&display=swap";
document.head.appendChild(fontLink);

// ─── Design tokens ───────────────────────────────────────────────────────────
const T = {
  soil:   "#1a1108",
  bark:   "#2d1f0e",
  amber:  "#c8711a",
  gold:   "#e8a830",
  cream:  "#fdf6e8",
  mist:   "#f5ede0",
  dusk:   "#8b6f4e",
  river:  "#2c5f6e",
  leaf:   "#3a6b3e",
  clay:   "#a04030",
  text:   "#1a1108",
  sub:    "#6b5240",
  rule:   "#d9c9b0",
  serif:  "'DM Serif Display', Georgia, serif",
  sans:   "'DM Sans', system-ui, sans-serif",
  mono:   "'DM Mono', monospace",
};

// ─── Language data ────────────────────────────────────────────────────────────
const LANGS = {
  chitonga:  { name:"ChiTonga",  iso:"toi", guthrie:"M.64", region:"Southern Province", color:T.river },
  chibemba:  { name:"Chibemba",  iso:"bem", guthrie:"M.42", region:"Copperbelt / Luapula", color:T.clay },
  chinyanja: { name:"ChiNyanja", iso:"nya", guthrie:"N.31", region:"Eastern Province / Lusaka", color:T.leaf },
  silozi:    { name:"SiLozi",    iso:"loz", guthrie:"K.21", region:"Western Province", color:T.amber },
  cikaonde:  { name:"ciKaonde",  iso:"kqn", guthrie:"L.41", region:"North-Western Province", color:T.dusk },
  ciluvale:  { name:"ciLuvale",  iso:"lue", guthrie:"K.14", region:"North-Western Province", color:"#5a7a3a" },
  cilunda:   { name:"ciLunda",   iso:"lun", guthrie:"L.52", region:"North-Western Province", color:"#6a4a7a" },
};

// ─── Word bank keyed by language ─────────────────────────────────────────────
const WORDS = {
  chitonga: [
    { word:"ubuntu",   nc:"NC14", prefix:"bu-",  plural:null,      gloss:"humanity; compassion for others",  pos:"noun",  example:"Ubuntu nduwe wakasolelwa."  },
    { word:"mwana",    nc:"NC1",  prefix:"mu-",  plural:"bana",    gloss:"child; son or daughter",           pos:"noun",  example:"Mwana uyu ulila."           },
    { word:"ng'anda",  nc:"NC9",  prefix:"N-",   plural:"ing'anda",gloss:"house; home",                      pos:"noun",  example:"Ng'anda ya Mweemba ili ciinda." },
    { word:"munzi",    nc:"NC3",  prefix:"mu-",  plural:"minzi",   gloss:"village; home settlement",         pos:"noun",  example:"Twaya kumunzi kwatusyalila." },
    { word:"maanzi",   nc:"NC6",  prefix:"ma-",  plural:null,      gloss:"water",                            pos:"noun",  example:"Maanzi aali buyo."          },
    { word:"kubona",   nc:"NC15", prefix:"ku-",  plural:null,      gloss:"to see; to understand",            pos:"verb",  example:"Ndabona luumuno lwako."      },
    { word:"bulelo",   nc:"NC14", prefix:"bu-",  plural:null,      gloss:"thanks; gratitude",                pos:"noun",  example:"Bulelo bwakwe tabwindi."    },
    { word:"nsimba",   nc:"NC9",  prefix:"N-",   plural:"nsimba",  gloss:"serval cat; small wild cat",       pos:"noun",  example:"Nsimba imoneka kabotu."     },
    { word:"kuyanda",  nc:"NC15", prefix:"ku-",  plural:null,      gloss:"to love; to want; to desire",      pos:"verb",  example:"Ndiyanda muntu woonse."     },
    { word:"ciindi",   nc:"NC7",  prefix:"ci-",  plural:"ziindi",  gloss:"time; season; period",             pos:"noun",  example:"Ciindi ca mbila citali."    },
    { word:"bupe",     nc:"NC14", prefix:"bu-",  plural:null,      gloss:"gift; generosity",                 pos:"noun",  example:"Bupe bwa Leza tabusoweki." },
    { word:"muntu",    nc:"NC1",  prefix:"mu-",  plural:"bantu",   gloss:"person; human being",              pos:"noun",  example:"Muntu woonse uyanda bulakalo." },
    { word:"luyando",  nc:"NC11", prefix:"lu-",  plural:null,      gloss:"love; affection (deep)",           pos:"noun",  example:"Luyando lukainda."          },
    { word:"busuma",   nc:"NC14", prefix:"bu-",  plural:null,      gloss:"goodness; well-being",             pos:"noun",  example:"Busuma bwako buyoowa."      },
  ],
  chibemba: [
    { word:"umuntu",   nc:"NC1",  prefix:"mu-",  plural:"abantu",  gloss:"person; human being",              pos:"noun",  example:"Umuntu nga umuntu ngabantu." },
    { word:"ubumi",    nc:"NC14", prefix:"bu-",  plural:null,      gloss:"life; existence",                  pos:"noun",  example:"Ubumi ni musebo uwamuyaya." },
    { word:"amano",    nc:"NC6",  prefix:"ma-",  plural:null,      gloss:"wisdom; knowledge; understanding", pos:"noun",  example:"Amano akonka inshiku."      },
    { word:"icipuba",  nc:"NC7",  prefix:"fi-",  plural:"ifipuba", gloss:"fool; foolishness; naivety",       pos:"noun",  example:"Icipuba tacisangwa amaningi." },
    { word:"amailo",   nc:"NC6",  prefix:"ma-",  plural:null,      gloss:"tomorrow; the future",             pos:"noun",  example:"Amailo natulolesha."        },
    { word:"ukutasha", nc:"NC15", prefix:"ku-",  plural:null,      gloss:"to thank; to praise",              pos:"verb",  example:"Natasha Lesa ilyo lya lyonse." },
  ],
  chinyanja: [
    { word:"munthu",   nc:"NC1",  prefix:"mu-",  plural:"anthu",   gloss:"person; human being",              pos:"noun",  example:"Munthu aliyense ali ndi moyo." },
    { word:"moyo",     nc:"NC3",  prefix:"mu-",  plural:"miyoyo",  gloss:"life; heart; soul",                pos:"noun",  example:"Moyo wake ndiwoyera kwambiri." },
    { word:"chifundo", nc:"NC7",  prefix:"chi-", plural:"zifundo", gloss:"mercy; compassion; kindness",      pos:"noun",  example:"Chifundo chake chisakanira." },
    { word:"dziko",    nc:"NC5",  prefix:"li-",  plural:"maiko",   gloss:"country; land; world",             pos:"noun",  example:"Dziko lathu ndi lakokoma."  },
    { word:"chikondi", nc:"NC7",  prefix:"chi-", plural:"zikondi", gloss:"love; affection",                  pos:"noun",  example:"Chikondi chake n'cholimba."  },
    { word:"kuona",    nc:"NC15", prefix:"ku-",  plural:null,      gloss:"to see; to look at",               pos:"verb",  example:"Ndikuona tsiku loyera."     },
  ],
  silozi: [
    { word:"mutu",     nc:"NC1",  prefix:"mo-",  plural:"batu",    gloss:"person; human being",              pos:"noun",  example:"Mutu kaufela u na ni tukufalelwa." },
    { word:"lizo",     nc:"NC11", prefix:"li-",  plural:"malizo",  gloss:"custom; tradition; way of life",   pos:"noun",  example:"Lizo la Malozi li yemela butali." },
    { word:"bulatwani",nc:"NC14", prefix:"bu-",  plural:null,      gloss:"peace; harmony; tranquility",      pos:"noun",  example:"Bulatwani ki nto ye nde."   },
    { word:"kutusa",   nc:"NC15", prefix:"ku-",  plural:null,      gloss:"to help; to assist",               pos:"verb",  example:"Kutusa mutu ki mulao wa Lozi." },
  ],
  cikaonde: [
    { word:"muntu",    nc:"NC1",  prefix:"mu-",  plural:"bantu",   gloss:"person; human being",              pos:"noun",  example:"Muntu wonso ali na mulandu." },
    { word:"bwino",    nc:"NC14", prefix:"bu-",  plural:null,      gloss:"goodness; well-being; health",     pos:"noun",  example:"Bwino bwako bwatatule."     },
    { word:"cintu",    nc:"NC7",  prefix:"ci-",  plural:"bintu",   gloss:"thing; object; matter",            pos:"noun",  example:"Cintu cyaakola cyafuma."   },
  ],
  ciluvale: [
    { word:"mwantu",   nc:"NC1",  prefix:"mu-",  plural:"antu",    gloss:"person; human being",              pos:"noun",  example:"Mwantu wose ali ne huma."   },
    { word:"wutayi",   nc:"NC14", prefix:"wu-",  plural:null,      gloss:"love; affection; care",            pos:"noun",  example:"Wutayi wakwe watakatuka."   },
    { word:"chinthu",  nc:"NC7",  prefix:"chi-", plural:"vinthuchinthu",gloss:"thing; item; matter",         pos:"noun",  example:"Chinthu che nawa chahuha."  },
  ],
  cilunda: [
    { word:"muntu",    nc:"NC1",  prefix:"mu-",  plural:"antu",    gloss:"person; human being",              pos:"noun",  example:"Muntu wose ali na kasongo." },
    { word:"busuma",   nc:"NC14", prefix:"bu-",  plural:null,      gloss:"goodness; prosperity",             pos:"noun",  example:"Busuma bwa Nzambi bwatupeta." },
    { word:"cintu",    nc:"NC7",  prefix:"ci-",  plural:"intu",    gloss:"thing; object",                    pos:"noun",  example:"Cintu cino cikeba."         },
  ],
};

// ─── Morphophonology (subset for paradigm explorer) ──────────────────────────
const VOWELS = new Set(['a','e','i','o','u','á','é','í','ó','ú']);
const MID_V  = new Set(['e','o']);

function hasMid(s){ return [...s.toLowerCase()].some(c=>MID_V.has(c)); }

function joinM(left, right) {
  if (!left) return right;
  if (!right) return left;
  const lc = left[left.length-1], rc = right[0];
  // SND.1: high-vowel glide
  if (VOWELS.has(rc)) {
    if (lc==='u') return left.slice(0,-1)+'w'+right;
    if (lc==='i') return left.slice(0,-1)+'y'+right;
  }
  // SND.2: coalescence (only a+vowel)
  if (lc==='a' && VOWELS.has(rc)) {
    const map = {'a':'a','i':'e','u':'o','e':'e','o':'o'};
    return left.slice(0,-1)+(map[rc]||rc)+right.slice(1);
  }
  return left+right;
}

function conjugate(sc, marker, root, fv, neg, negType, negPre, negInfix) {
  // strip trailing -a from root before vowel-initial FV
  const stem = (root.endsWith('a') && fv && VOWELS.has(fv[0])) ? root.slice(0,-1) : root;
  const parts = [];
  if (neg && negType==='pre' && negPre) parts.push(negPre);
  parts.push(sc);
  if (neg && negType==='infix' && negInfix) parts.push(negInfix);
  if (!neg && marker) parts.push(marker);  // suppress TAM in negatives
  parts.push(stem);
  parts.push(fv);
  return parts.reduce((acc,p) => joinM(acc,p));
}

// ─── Grammar configs ──────────────────────────────────────────────────────────
const GRAM = {
  chitonga: {
    neg_type:'pre', neg_pre:'ta', neg_infix:'',
    tam:{ PRES:{l:'Present',mk:'a',fv:'a',nfv:'i'}, PST:{l:'Past',mk:'aka',fv:'a',nfv:'i'},
          FUT:{l:'Future',mk:'yo',fv:'a',nfv:'i'}, PERF:{l:'Perfect',mk:'a',fv:'ide',nfv:'i'},
          HAB:{l:'Habitual',mk:'la',fv:'a',nfv:'i'}, SUBJ:{l:'Subjunctive',mk:'',fv:'e',nfv:'e'} },
    defTam:['PRES','PST','FUT','PERF'],
    sc:[ {id:'1SG',f:'ndi',bv:'nd',l:'I',s:'1SG'},
         {id:'2SG',f:'u',  l:'you',s:'2SG'},{id:'3SG',f:'u',l:'he/she',s:'3SG'},
         {id:'1PL',f:'tu', l:'we',s:'1PL'},{id:'2PL',f:'mu',l:'you(pl)',s:'2PL'},
         {id:'3PL',f:'ba', l:'they',s:'3PL'},
         null,
         {id:'NC1',f:'u', l:'NC1',s:'mu- human sg'},{id:'NC2',f:'ba',l:'NC2',s:'ba- humans pl'},
         {id:'NC3',f:'u', l:'NC3',s:'mu- tree sg'},{id:'NC4',f:'i',l:'NC4',s:'mi- trees pl'},
         {id:'NC5',f:'li',l:'NC5',s:'li- body part sg'},{id:'NC6',f:'a',l:'NC6',s:'ma- mass'},
         {id:'NC7',f:'ci',l:'NC7',s:'ci- thing sg'},{id:'NC8',f:'zi',l:'NC8',s:'zi- things pl'},
         {id:'NC9',f:'i', l:'NC9',s:'N- animal sg'},{id:'NC10',f:'zi',l:'NC10',s:'N- animals pl'},
         {id:'NC11',f:'lu',l:'NC11',s:'lu- long obj'},{id:'NC14',f:'bu',l:'NC14',s:'bu- abstract'},
         {id:'NC15',f:'ku',l:'NC15',s:'ku- infinitive'},
         null,
         {id:'NC16',f:'pa',l:'NC16',s:'pa- at/on'},{id:'NC17',f:'ku',l:'NC17',s:'ku- towards'},
         {id:'NC18',f:'mu',l:'NC18',s:'mu- inside'} ],
  },
  chibemba: {
    neg_type:'pre', neg_pre:'ta', neg_infix:'',
    tam:{ PRES:{l:'Present',mk:'a',fv:'a',nfv:'i'}, PST:{l:'Past',mk:'na',fv:'a',nfv:'i'},
          FUT:{l:'Future',mk:'laa',fv:'a',nfv:'i'}, PERF:{l:'Perfect',mk:'a',fv:'ile',nfv:'i'},
          SUBJ:{l:'Subjunctive',mk:'',fv:'e',nfv:'e'} },
    defTam:['PRES','PST','FUT','PERF'],
    sc:[ {id:'1SG',f:'ndi',bv:'nd',l:'I',s:'1SG'},
         {id:'2SG',f:'u',l:'you',s:'2SG'},{id:'3SG',f:'u',l:'he/she',s:'3SG'},
         {id:'1PL',f:'tu',l:'we',s:'1PL'},{id:'2PL',f:'mu',l:'you(pl)',s:'2PL'},
         {id:'3PL',f:'ba',l:'they',s:'3PL'},
         null,
         {id:'NC1',f:'u',l:'NC1',s:'mu- human sg'},{id:'NC2',f:'ba',l:'NC2',s:'ba- humans pl'},
         {id:'NC3',f:'u',l:'NC3',s:'mu- tree sg'},{id:'NC4',f:'i',l:'NC4',s:'mi- trees pl'},
         {id:'NC7',f:'fi',l:'NC7',s:'fi- thing sg'},{id:'NC8',f:'bi',l:'NC8',s:'bi- things pl'},
         {id:'NC9',f:'i',l:'NC9',s:'N- animal sg'},{id:'NC14',f:'bu',l:'NC14',s:'bu- abstract'},
         {id:'NC15',f:'ku',l:'NC15',s:'ku- infinitive'},
         null,
         {id:'NC16',f:'pa',l:'NC16',s:'pa- at/on'},{id:'NC17',f:'ku',l:'NC17',s:'ku- towards'},
         {id:'NC18',f:'mu',l:'NC18',s:'mu- inside'} ],
  },
  chinyanja: {
    neg_type:'infix', neg_pre:'', neg_infix:'sa',
    tam:{ PRES:{l:'Present',mk:'ma',fv:'a',nfv:'a'}, PST:{l:'Past',mk:'na',fv:'a',nfv:'a'},
          FUT:{l:'Future',mk:'dza',fv:'a',nfv:'a'}, SUBJ:{l:'Subjunctive',mk:'',fv:'e',nfv:'e'},
          PROG:{l:'Progressive',mk:'ku',fv:'a',nfv:'a'} },
    defTam:['PRES','PST','FUT'],
    sc:[ {id:'1SG',f:'ndi',bv:'nd',l:'I',s:'1SG'},
         {id:'2SG',f:'u',l:'you',s:'2SG'},{id:'3SG',f:'u',l:'he/she',s:'3SG'},
         {id:'1PL',f:'ti',l:'we',s:'1PL'},{id:'2PL',f:'mu',l:'you(pl)',s:'2PL'},
         {id:'3PL',f:'a',l:'they',s:'3PL'},
         null,
         {id:'NC1',f:'u',l:'NC1',s:'mu- human sg'},{id:'NC2',f:'a',l:'NC2',s:'a- humans pl'},
         {id:'NC3',f:'u',l:'NC3',s:'mu- tree sg'},{id:'NC4',f:'i',l:'NC4',s:'mi- trees pl'},
         {id:'NC7',f:'chi',l:'NC7',s:'chi- thing sg'},{id:'NC8',f:'zi',l:'NC8',s:'zi- things pl'},
         {id:'NC9',f:'i',l:'NC9',s:'N- animal sg'},{id:'NC14',f:'u',l:'NC14',s:'u- abstract'},
         {id:'NC15',f:'ku',l:'NC15',s:'ku- infinitive'},
         null,
         {id:'NC16',f:'pa',l:'NC16',s:'pa- at/on'},{id:'NC17',f:'ku',l:'NC17',s:'ku- towards'},
         {id:'NC18',f:'mu',l:'NC18',s:'mu- inside'} ],
  },
  silozi: {
    neg_type:'pre', neg_pre:'ha', neg_infix:'',
    tam:{ PRES:{l:'Present',mk:'a',fv:'a',nfv:'i'}, PST:{l:'Past',mk:'ne',fv:'ile',nfv:'ile'},
          FUT:{l:'Future',mk:'ka',fv:'a',nfv:'i'}, PERF:{l:'Perfect',mk:'a',fv:'ile',nfv:'i'},
          SUBJ:{l:'Subjunctive',mk:'',fv:'e',nfv:'e'} },
    defTam:['PRES','PST','FUT'],
    sc:[ {id:'1SG',f:'ni',l:'I',s:'1SG'},
         {id:'2SG',f:'u',l:'you',s:'2SG'},{id:'3SG',f:'u',l:'he/she',s:'3SG'},
         {id:'1PL',f:'lu',l:'we',s:'1PL'},{id:'2PL',f:'mu',l:'you(pl)',s:'2PL'},
         {id:'3PL',f:'ba',l:'they',s:'3PL'},
         null,
         {id:'NC1',f:'u',l:'NC1',s:'mo- human sg'},{id:'NC2',f:'ba',l:'NC2',s:'ba- humans pl'},
         {id:'NC7',f:'si',l:'NC7',s:'si- thing sg'},{id:'NC8',f:'li',l:'NC8',s:'li- things pl'},
         {id:'NC14',f:'bu',l:'NC14',s:'bu- abstract'},{id:'NC15',f:'ku',l:'NC15',s:'ku- infinitive'},
         null,
         {id:'NC16',f:'fa',l:'NC16',s:'fa- at/on'},{id:'NC17',f:'ku',l:'NC17',s:'ku- towards'},
         {id:'NC18',f:'mu',l:'NC18',s:'mu- inside'} ],
  },
  cikaonde: {
    neg_type:'pre', neg_pre:'ta', neg_infix:'',
    tam:{ PRES:{l:'Present',mk:'a',fv:'a',nfv:'i'}, PST:{l:'Past',mk:'aka',fv:'ile',nfv:'i'},
          FUT:{l:'Future',mk:'yo',fv:'a',nfv:'i'}, SUBJ:{l:'Subjunctive',mk:'',fv:'e',nfv:'e'} },
    defTam:['PRES','PST','FUT'],
    sc:[ {id:'1SG',f:'ndi',bv:'nd',l:'I',s:'1SG'},
         {id:'2SG',f:'u',l:'you',s:'2SG'},{id:'3SG',f:'u',l:'he/she',s:'3SG'},
         {id:'1PL',f:'tu',l:'we',s:'1PL'},{id:'2PL',f:'mu',l:'you(pl)',s:'2PL'},
         {id:'3PL',f:'ba',l:'they',s:'3PL'},
         null,
         {id:'NC1',f:'u',l:'NC1',s:'mu- human sg'},{id:'NC2',f:'ba',l:'NC2',s:'ba- humans pl'},
         {id:'NC7',f:'ci',l:'NC7',s:'ci- thing sg'},{id:'NC8',f:'bi',l:'NC8',s:'bi- things pl'},
         {id:'NC14',f:'bu',l:'NC14',s:'bu- abstract'},{id:'NC15',f:'ku',l:'NC15',s:'ku- infinitive'} ],
  },
  ciluvale: {
    neg_type:'pre', neg_pre:'ka', neg_infix:'',
    tam:{ PRES:{l:'Present',mk:'a',fv:'a',nfv:'i'}, PST:{l:'Past',mk:'aka',fv:'ile',nfv:'i'},
          FUT:{l:'Future',mk:'yo',fv:'a',nfv:'i'}, SUBJ:{l:'Subjunctive',mk:'',fv:'e',nfv:'e'} },
    defTam:['PRES','PST','FUT'],
    sc:[ {id:'1SG',f:'ndi',bv:'nd',l:'I',s:'1SG'},
         {id:'2SG',f:'u',l:'you',s:'2SG'},{id:'3SG',f:'u',l:'he/she',s:'3SG'},
         {id:'1PL',f:'tu',l:'we',s:'1PL'},{id:'2PL',f:'mu',l:'you(pl)',s:'2PL'},
         {id:'3PL',f:'a',l:'they',s:'3PL'},
         null,
         {id:'NC1',f:'u',l:'NC1',s:'mu- human sg'},{id:'NC2',f:'a',l:'NC2',s:'a- humans pl'},
         {id:'NC7',f:'chi',l:'NC7',s:'chi- thing sg'},{id:'NC8',f:'vi',l:'NC8',s:'vi- things pl'},
         {id:'NC14',f:'bu',l:'NC14',s:'bu- abstract'},{id:'NC15',f:'ku',l:'NC15',s:'ku- infinitive'} ],
  },
  cilunda: {
    neg_type:'pre', neg_pre:'ta', neg_infix:'',
    tam:{ PRES:{l:'Present',mk:'a',fv:'a',nfv:'i'}, PST:{l:'Past',mk:'aka',fv:'ile',nfv:'i'},
          FUT:{l:'Future',mk:'yo',fv:'a',nfv:'i'}, SUBJ:{l:'Subjunctive',mk:'',fv:'e',nfv:'e'} },
    defTam:['PRES','PST','FUT'],
    sc:[ {id:'1SG',f:'ndi',bv:'nd',l:'I',s:'1SG'},
         {id:'2SG',f:'u',l:'you',s:'2SG'},{id:'3SG',f:'u',l:'he/she',s:'3SG'},
         {id:'1PL',f:'tu',l:'we',s:'1PL'},{id:'2PL',f:'mu',l:'you(pl)',s:'2PL'},
         {id:'3PL',f:'a',l:'they',s:'3PL'},
         null,
         {id:'NC1',f:'u',l:'NC1',s:'mu- human sg'},{id:'NC2',f:'a',l:'NC2',s:'a- humans pl'},
         {id:'NC7',f:'ci',l:'NC7',s:'ci- thing sg'},{id:'NC8',f:'i',l:'NC8',s:'i- things pl'},
         {id:'NC14',f:'bu',l:'NC14',s:'bu- abstract'},{id:'NC15',f:'ku',l:'NC15',s:'ku- infinitive'} ],
  },
};

// ─── Date helpers ─────────────────────────────────────────────────────────────
function todayWord(lang) {
  const pool = WORDS[lang] || WORDS.chitonga;
  const d = new Date();
  const seed = d.getFullYear()*10000 + (d.getMonth()+1)*100 + d.getDate();
  return pool[seed % pool.length];
}

function formatDate() {
  return new Date().toLocaleDateString('en-GB',{day:'numeric',month:'long',year:'numeric'});
}

// ─── Card theme presets ───────────────────────────────────────────────────────
const THEMES = [
  { name:"Savanna",  bg:"#1a1108", fg:"#fdf6e8", accent:"#e8a830", sub:"#c8a870",  geo:"#2d1f0e" },
  { name:"Baobab",   bg:"#0d1f2d", fg:"#e8f4ea", accent:"#5fad7e", sub:"#7db89a",  geo:"#142534" },
  { name:"Kalahari", bg:"#2d1518", fg:"#faeee8", accent:"#e05a38", sub:"#c88070",  geo:"#3d2020" },
  { name:"Indigo",   bg:"#0f0f2a", fg:"#e8e8ff", accent:"#a090ff", sub:"#8878cc",  geo:"#18183a" },
  { name:"Clay",     bg:"#f5ede0", fg:"#1a1108", accent:"#c8711a", sub:"#8b6f4e",  geo:"#e8d8c0" },
  { name:"Malachite",bg:"#0a1f12", fg:"#e8faf0", accent:"#40c878", sub:"#60a878",  geo:"#0f2a1a" },
];

// ─── Shared UI atoms ──────────────────────────────────────────────────────────
const ss = (x) => ({ fontFamily:T.sans, ...x });
const sm = (x) => ({ fontFamily:T.mono, ...x });

function LangPill({ langKey, active, onClick }) {
  const l = LANGS[langKey];
  return (
    <button onClick={onClick} style={{
      padding:'5px 13px', borderRadius:20, fontSize:11, cursor:'pointer',
      fontFamily:T.sans, fontWeight:500, transition:'all 0.15s',
      background: active ? l.color : 'transparent',
      color: active ? '#fff' : T.dusk,
      border: `1.5px solid ${active ? l.color : T.rule}`,
    }}>{l.name}</button>
  );
}

// ─── NAV ──────────────────────────────────────────────────────────────────────
function Nav({ tab, setTab }) {
  return (
    <nav style={{ background:T.soil, padding:'0 32px', display:'flex', alignItems:'center',
      gap:0, position:'sticky', top:0, zIndex:100, borderBottom:`2px solid ${T.bark}` }}>
      <div style={{ fontFamily:T.serif, fontSize:18, color:T.cream, marginRight:32,
        letterSpacing:'-0.01em', paddingTop:2 }}>
        Gobelo
        <span style={{ fontStyle:'italic', color:T.gold }}> Platform</span>
      </div>
      {[
        { id:'wotd', label:'Word of the Day' },
        { id:'paradigm', label:'Paradigm Explorer' },
      ].map(({id,label}) => (
        <button key={id} onClick={()=>setTab(id)} style={{
          padding:'16px 20px', background:'none', border:'none', cursor:'pointer',
          fontFamily:T.sans, fontSize:13, fontWeight:500, transition:'all 0.15s',
          color: tab===id ? T.gold : T.dusk,
          borderBottom: tab===id ? `2px solid ${T.gold}` : '2px solid transparent',
          marginBottom: -2,
        }}>{label}</button>
      ))}
      <div style={{ flex:1 }}/>
      <span style={{ fontSize:10, color:T.dusk, fontFamily:T.mono,
        letterSpacing:'0.1em' }}>gobelo.zambantutools.org</span>
    </nav>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// WORD OF THE DAY
// ═══════════════════════════════════════════════════════════════════════════════
function WordOfTheDay() {
  const [lang, setLang]       = useState('chitonga');
  const [word, setWord]       = useState(() => todayWord('chitonga'));
  const [theme, setTheme]     = useState(0);
  const [custom, setCustom]   = useState(false);
  const [customW, setCustomW] = useState({ word:'', gloss:'', nc:'NC1',
    prefix:'mu-', plural:'', example:'', pos:'noun' });
  const [showIdx, setShowIdx] = useState(null);
  const [aiSentence, setAiSentence]   = useState('');
  const [aiLoading, setAiLoading]     = useState(false);
  const [copied, setCopied]           = useState(false);
  const cardRef = useRef(null);
  const TH = THEMES[theme];
  const activeWord = custom ? customW : word;
  const L = LANGS[lang];

  function pickLang(k) {
    setLang(k);
    setWord(todayWord(k));
    setCustom(false);
    setAiSentence('');
  }

  function pickWord(w) {
    setWord(w);
    setCustom(false);
    setAiSentence('');
    setShowIdx(null);
  }

  async function generateSentence() {
    setAiLoading(true);
    setAiSentence('');
    try {
      const res = await fetch('https://api.anthropic.com/v1/messages', {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({
          model:'claude-sonnet-4-20250514', max_tokens:200,
          messages:[{ role:'user', content:
            `Write ONE short, natural example sentence in ${L.name} using the word "${activeWord.word}" (meaning: ${activeWord.gloss}). ` +
            `Then on the next line write the English translation. Format exactly as:\n${L.name}: [sentence]\nEnglish: [translation]\n` +
            `Keep it culturally relevant to Zambia. The sentence should be simple and clear.`
          }]
        })
      });
      const d = await res.json();
      const text = d.content?.find(c=>c.type==='text')?.text || '';
      setAiSentence(text.trim());
    } catch { setAiSentence('Could not generate — check API.'); }
    setAiLoading(false);
  }

  function copyShareText() {
    const ex = aiSentence || activeWord.example || '';
    const txt = `📖 Word of the Day — ${L.name}\n\n${activeWord.word}\n"${activeWord.gloss}"\n\n${ex}\n\n— Gobelo Platform · gobelo.zambantutools.org`;
    navigator.clipboard?.writeText(txt).catch(()=>{});
    setCopied(true); setTimeout(()=>setCopied(false),2000);
  }

  const pool = WORDS[lang] || [];

  return (
    <div style={{ display:'flex', gap:0, minHeight:'calc(100vh - 56px)' }}>

      {/* ── LEFT PANEL ── */}
      <div style={{ width:280, flexShrink:0, padding:'24px 20px',
        background:'#fff', borderRight:`1px solid ${T.rule}`,
        overflowY:'auto', display:'flex', flexDirection:'column', gap:20 }}>

        {/* Language */}
        <div>
          <div style={ss({fontSize:9,fontWeight:600,letterSpacing:'0.14em',
            textTransform:'uppercase',color:T.sub,marginBottom:8})}>Language</div>
          <div style={{ display:'flex', flexWrap:'wrap', gap:5 }}>
            {Object.keys(LANGS).map(k=>(
              <LangPill key={k} langKey={k} active={lang===k} onClick={()=>pickLang(k)}/>
            ))}
          </div>
        </div>

        {/* Word picker */}
        <div>
          <div style={ss({fontSize:9,fontWeight:600,letterSpacing:'0.14em',
            textTransform:'uppercase',color:T.sub,marginBottom:8})}>Choose word</div>
          <div style={{ display:'flex',flexDirection:'column',gap:3 }}>
            {pool.map((w,i)=>(
              <button key={i} onClick={()=>pickWord(w)} style={{
                textAlign:'left', padding:'7px 10px', borderRadius:6,
                border:`1px solid ${!custom&&word===w ? L.color : T.rule}`,
                background: !custom&&word===w ? L.color+'11' : 'transparent',
                cursor:'pointer', display:'flex', justifyContent:'space-between',
                alignItems:'center',
              }}>
                <span style={sm({fontSize:12,fontWeight:500,color:T.text})}>{w.word}</span>
                <span style={ss({fontSize:9,color:T.sub})}>{w.nc}</span>
              </button>
            ))}
            {pool.length === 0 && (
              <div style={ss({fontSize:11,color:T.sub,padding:'8px 0'})}>
                More words coming — add them via the Grammar Admin.
              </div>
            )}
          </div>
        </div>

        {/* Custom entry */}
        <div>
          <div style={ss({fontSize:9,fontWeight:600,letterSpacing:'0.14em',
            textTransform:'uppercase',color:T.sub,marginBottom:8})}>Custom word</div>
          <div style={{ display:'flex',flexDirection:'column',gap:6 }}>
            {[['word','Word'],['gloss','Meaning'],['nc','NC class'],
              ['prefix','Prefix'],['plural','Plural form'],['example','Example sentence']
            ].map(([k,l])=>(
              <div key={k}>
                <div style={ss({fontSize:10,color:T.sub,marginBottom:2})}>{l}</div>
                <input value={customW[k]} placeholder={l}
                  onChange={e=>{ setCustom(true); setCustomW(p=>({...p,[k]:e.target.value})); }}
                  style={{ width:'100%',padding:'5px 8px',border:`1px solid ${T.rule}`,
                    borderRadius:4,fontSize:12,fontFamily:T.sans,outline:'none',
                    background:'#fafaf8' }}/>
              </div>
            ))}
          </div>
        </div>

        {/* Card theme */}
        <div>
          <div style={ss({fontSize:9,fontWeight:600,letterSpacing:'0.14em',
            textTransform:'uppercase',color:T.sub,marginBottom:8})}>Card theme</div>
          <div style={{ display:'flex',flexWrap:'wrap',gap:6 }}>
            {THEMES.map((th,i)=>(
              <button key={i} onClick={()=>setTheme(i)} title={th.name} style={{
                width:24,height:24,borderRadius:'50%',border:`2px solid ${i===theme?th.accent:'transparent'}`,
                background:th.bg,cursor:'pointer',boxShadow:`0 0 0 1px ${T.rule}`,
              }}/>
            ))}
          </div>
        </div>
      </div>

      {/* ── CARD PREVIEW ── */}
      <div style={{ flex:1, background:T.mist, display:'flex', flexDirection:'column',
        alignItems:'center', padding:'32px 24px', gap:24, overflowY:'auto' }}>

        {/* The card */}
        <div ref={cardRef} style={{
          width:480, background:TH.bg, borderRadius:16, overflow:'hidden',
          boxShadow:'0 8px 48px rgba(0,0,0,0.2)', position:'relative',
          cursor:'default', userSelect:'none',
        }}>
          {/* Decorative geometry */}
          <svg width="480" height="12" style={{ display:'block' }}>
            <rect width="480" height="12" fill={TH.accent}/>
          </svg>
          <svg width="480" height="80" style={{ display:'block', marginTop:-12,
            position:'absolute', top:12, left:0, opacity:0.07 }}>
            <circle cx="380" cy="40" r="120" fill={TH.fg}/>
            <circle cx="60"  cy="70" r="80"  fill={TH.fg}/>
          </svg>

          {/* Card header */}
          <div style={{ padding:'20px 24px 0', position:'relative' }}>
            <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start' }}>
              <div>
                <div style={ss({fontSize:9,letterSpacing:'0.22em',textTransform:'uppercase',
                  color:TH.accent,marginBottom:2,fontWeight:600})}>
                  {L.name} · Word of the Day
                </div>
                <div style={ss({fontSize:10,color:TH.sub})}>{formatDate()}</div>
              </div>
              <div style={{ textAlign:'right' }}>
                <div style={ss({fontSize:8,color:TH.sub,letterSpacing:'0.1em',
                  textTransform:'uppercase'})}>Gobelo Platform</div>
              </div>
            </div>
          </div>

          {/* Main word */}
          <div style={{ padding:'18px 24px 0' }}>
            <div style={{ fontFamily:T.serif, fontSize:52, color:TH.fg,
              letterSpacing:'-0.03em', lineHeight:1, marginBottom:4 }}>
              {activeWord.word || '—'}
            </div>
            <div style={ss({fontSize:13,color:TH.accent,fontStyle:'italic',
              marginBottom:12})}>{activeWord.gloss || 'Enter a gloss above'}</div>
          </div>

          {/* NC / prefix / plural chips */}
          <div style={{ padding:'0 24px 16px', display:'flex', gap:6, flexWrap:'wrap' }}>
            {activeWord.nc && (
              <span style={{ padding:'3px 10px', borderRadius:4, fontSize:10,
                background:TH.geo, color:TH.accent, fontFamily:T.mono,
                border:`1px solid ${TH.accent}33`, fontWeight:600 }}>
                {activeWord.nc}
              </span>
            )}
            {activeWord.prefix && (
              <span style={{ padding:'3px 10px', borderRadius:4, fontSize:10,
                background:TH.geo, color:TH.sub, fontFamily:T.mono }}>
                prefix: {activeWord.prefix}
              </span>
            )}
            {activeWord.plural && (
              <span style={{ padding:'3px 10px', borderRadius:4, fontSize:10,
                background:TH.geo, color:TH.sub, fontFamily:T.mono }}>
                pl: {activeWord.plural}
              </span>
            )}
            {activeWord.pos && (
              <span style={{ padding:'3px 10px', borderRadius:4, fontSize:10,
                background:TH.geo, color:TH.sub, fontFamily:T.sans }}>
                {activeWord.pos}
              </span>
            )}
          </div>

          {/* Divider */}
          <div style={{ margin:'0 24px', height:1, background:`${TH.fg}18` }}/>

          {/* Example sentence */}
          <div style={{ padding:'14px 24px 20px' }}>
            <div style={ss({fontSize:9,letterSpacing:'0.12em',textTransform:'uppercase',
              color:TH.sub,marginBottom:6,fontWeight:600})}>Example</div>
            {aiSentence ? (
              <div style={ss({fontSize:12,color:TH.fg,lineHeight:1.7,whiteSpace:'pre-line'})}>
                {aiSentence}
              </div>
            ) : (
              <div style={ss({fontSize:13,color:`${TH.fg}cc`,lineHeight:1.7,fontStyle:'italic'})}>
                {activeWord.example || 'Add an example sentence above'}
              </div>
            )}
          </div>

          {/* Footer bar */}
          <div style={{ background:TH.geo, padding:'10px 24px',
            display:'flex', justifyContent:'space-between', alignItems:'center' }}>
            <div style={ss({fontSize:8,color:TH.sub,letterSpacing:'0.08em'})}>
              {L.guthrie} · {L.region}
            </div>
            <div style={ss({fontSize:8,color:TH.accent,letterSpacing:'0.1em',
              textTransform:'uppercase',fontWeight:600})}>
              gobelo.zambantutools.org
            </div>
          </div>
        </div>

        {/* Action buttons */}
        <div style={{ display:'flex', gap:10, flexWrap:'wrap', justifyContent:'center' }}>
          <button onClick={generateSentence} disabled={aiLoading} style={{
            padding:'10px 20px', borderRadius:6, border:'none', cursor:'pointer',
            background:L.color, color:'#fff', fontFamily:T.sans, fontSize:12,
            fontWeight:600, opacity:aiLoading?0.7:1,
          }}>
            {aiLoading ? 'Generating…' : '✦ AI example sentence'}
          </button>
          <button onClick={copyShareText} style={{
            padding:'10px 20px', borderRadius:6, cursor:'pointer',
            background: copied?T.leaf:'#fff', color: copied?'#fff':T.soil,
            border:`1.5px solid ${copied?T.leaf:T.rule}`,
            fontFamily:T.sans, fontSize:12, fontWeight:500,
          }}>
            {copied ? '✓ Copied!' : '⎘ Copy share text'}
          </button>
        </div>

        {/* Social size guide */}
        <div style={{ padding:'12px 20px', background:'#fff', borderRadius:8,
          border:`1px solid ${T.rule}`, maxWidth:480, width:'100%' }}>
          <div style={ss({fontSize:9,fontWeight:600,letterSpacing:'0.12em',
            textTransform:'uppercase',color:T.sub,marginBottom:8})}>Share on</div>
          <div style={{ display:'flex', gap:12, flexWrap:'wrap' }}>
            {[['WhatsApp','1:1 · 1080×1080','#25d366'],
              ['Facebook','1.91:1 · 1200×628','#1877f2'],
              ['Twitter/X','16:9 · 1200×675','#111']
            ].map(([pl,sz,c])=>(
              <div key={pl} style={{ display:'flex',alignItems:'center',gap:6 }}>
                <div style={{ width:8,height:8,borderRadius:'50%',background:c,flexShrink:0 }}/>
                <span style={ss({fontSize:10,color:T.text})}>{pl}</span>
                <span style={sm({fontSize:9,color:T.sub})}>{sz}</span>
              </div>
            ))}
          </div>
          <div style={ss({fontSize:10,color:T.sub,marginTop:8,lineHeight:1.5})}>
            Use your browser's screenshot tool or screenshot this card area.
            A backend PDF/image export can be added via Puppeteer.
          </div>
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// PARADIGM EXPLORER
// ═══════════════════════════════════════════════════════════════════════════════
function ParadigmExplorer() {
  const [lang,     setLang]     = useState('chitonga');
  const [root,     setRoot]     = useState('bona');
  const [gloss,    setGloss]    = useState('to see');
  const [selTam,   setSelTam]   = useState({PRES:true,PST:true,FUT:true,PERF:true});
  const [showNeg,  setShowNeg]  = useState(false);
  const [showLoc,  setShowLoc]  = useState(false);
  const [highlight,setHighlight]= useState(null);
  const [copied,   setCopied]   = useState(false);
  const tableRef = useRef(null);
  const L  = LANGS[lang];
  const G  = GRAM[lang];
  const ordered = Object.keys(G.tam);
  const active  = ordered.filter(k=>selTam[k]);

  function toggleTam(k){ setSelTam(p=>({...p,[k]:!p[k]})); }

  function getForm(sc, tamId, neg) {
    const t = G.tam[tamId];
    const scForm = sc.bv && (t.mk||root)[0] && VOWELS.has((t.mk||root)[0]) ? sc.bv : sc.f;
    return conjugate(scForm, t.mk, root||'bona', neg?t.nfv:t.fv,
                     neg, G.neg_type, G.neg_pre, G.neg_infix);
  }

  function copyURL() {
    const url = `https://gobelo.zambantutools.org/paradigm?lang=${lang}&verb=${encodeURIComponent(root)}&gloss=${encodeURIComponent(gloss)}&tam=${active.join(',')}`;
    navigator.clipboard?.writeText(url).catch(()=>{});
    setCopied(true); setTimeout(()=>setCopied(false),2000);
  }

  // Groups of SCs (split by null separators in the array)
  const groups = [];
  let cur = [];
  for (const sc of G.sc) {
    if (sc === null) { if (cur.length) groups.push(cur); cur = []; }
    else cur.push(sc);
  }
  if (cur.length) groups.push(cur);

  const groupColors = [
    { bg:'#fffbf3', label:'Personal' },
    { bg:'#f4f9f5', label:'Noun classes' },
    { bg:'#f4f4fb', label:'Locative' },
  ];

  const nCols = active.length * (showNeg ? 2 : 1);

  return (
    <div style={{ display:'flex', gap:0, minHeight:'calc(100vh - 56px)' }}>

      {/* ── SIDEBAR ── */}
      <div style={{ width:252, flexShrink:0, background:'#fff',
        borderRight:`1px solid ${T.rule}`, padding:'20px 16px',
        display:'flex', flexDirection:'column', gap:18, overflowY:'auto' }}>

        <div>
          <div style={ss({fontSize:9,fontWeight:600,letterSpacing:'0.14em',
            textTransform:'uppercase',color:T.sub,marginBottom:8})}>Language</div>
          <div style={{ display:'flex',flexWrap:'wrap',gap:4 }}>
            {Object.keys(LANGS).map(k=>(
              <LangPill key={k} langKey={k} active={lang===k}
                onClick={()=>{ setLang(k); setSelTam(Object.fromEntries(GRAM[k].defTam.map(t=>[t,true]))); }}/>
            ))}
          </div>
        </div>

        <div>
          <div style={ss({fontSize:9,fontWeight:600,letterSpacing:'0.14em',
            textTransform:'uppercase',color:T.sub,marginBottom:8})}>Verb</div>
          <div style={ss({fontSize:10,color:T.sub,marginBottom:3})}>Root (no hyphens)</div>
          <input value={root} onChange={e=>setRoot(e.target.value)} placeholder="e.g. bona"
            style={{ width:'100%',padding:'6px 9px',border:`1px solid ${T.rule}`,
              borderRadius:5,fontSize:13,fontFamily:T.mono,outline:'none' }}/>
          <div style={ss({fontSize:10,color:T.sub,marginBottom:3,marginTop:8})}>Gloss</div>
          <input value={gloss} onChange={e=>setGloss(e.target.value)} placeholder="e.g. to see"
            style={{ width:'100%',padding:'6px 9px',border:`1px solid ${T.rule}`,
              borderRadius:5,fontSize:12,fontFamily:T.sans,outline:'none' }}/>
        </div>

        <div>
          <div style={ss({fontSize:9,fontWeight:600,letterSpacing:'0.14em',
            textTransform:'uppercase',color:T.sub,marginBottom:8})}>TAM forms</div>
          <div style={{ display:'flex',flexDirection:'column',gap:4 }}>
            {ordered.map(k=>{
              const t = G.tam[k];
              return (
                <label key={k} style={{ display:'flex',alignItems:'center',gap:8,
                  cursor:'pointer',padding:'5px 8px',borderRadius:5,
                  background:selTam[k]?L.color+'11':'transparent',
                  border:`1px solid ${selTam[k]?L.color:T.rule}`,
                }}>
                  <input type="checkbox" checked={!!selTam[k]}
                    onChange={()=>toggleTam(k)}
                    style={{ accentColor:L.color,width:13,height:13,cursor:'pointer' }}/>
                  <span style={ss({fontSize:11,color:T.text,flex:1})}>{t.l}</span>
                  <span style={sm({fontSize:9,color:T.sub})}>{t.mk||'∅'}…{t.fv}</span>
                </label>
              );
            })}
          </div>
        </div>

        <div>
          <div style={ss({fontSize:9,fontWeight:600,letterSpacing:'0.14em',
            textTransform:'uppercase',color:T.sub,marginBottom:8})}>Options</div>
          {[['showNeg','Negative forms',showNeg,setShowNeg],
            ['showLoc','Locative classes',showLoc,setShowLoc]
          ].map(([id,label,val,set])=>(
            <label key={id} style={{ display:'flex',alignItems:'center',gap:8,
              cursor:'pointer',marginBottom:6 }}>
              <input type="checkbox" checked={val} onChange={()=>set(!val)}
                style={{ accentColor:T.amber,width:13,height:13,cursor:'pointer' }}/>
              <span style={ss({fontSize:11,color:T.text})}>{label}</span>
            </label>
          ))}
        </div>

        <div style={{ marginTop:'auto' }}>
          <button onClick={copyURL} style={{
            width:'100%',padding:'9px',borderRadius:6,cursor:'pointer',
            background:copied?T.leaf:'transparent',
            color:copied?'#fff':T.soil,
            border:`1.5px solid ${copied?T.leaf:T.rule}`,
            fontFamily:T.sans,fontSize:12,fontWeight:500,
          }}>
            {copied ? '✓ URL copied!' : '⎘ Copy shareable URL'}
          </button>
        </div>
      </div>

      {/* ── TABLE ── */}
      <div style={{ flex:1, overflowX:'auto', overflowY:'auto',
        background:T.mist, padding:'24px' }}>

        {active.length === 0 ? (
          <div style={ss({textAlign:'center',padding:80,color:T.dusk,fontSize:13})}>
            Select at least one TAM form to see the paradigm.
          </div>
        ) : (
          <div ref={tableRef} style={{ background:'#fff', borderRadius:12,
            overflow:'hidden', boxShadow:'0 2px 16px rgba(0,0,0,0.08)',
            minWidth: 480, maxWidth: 1100, }}>

            {/* Table header */}
            <div style={{ padding:'18px 24px 14px', borderBottom:`2px solid ${T.soil}`,
              display:'flex', justifyContent:'space-between', alignItems:'flex-end',
              background:T.soil }}>
              <div>
                <div style={ss({fontSize:9,letterSpacing:'0.2em',textTransform:'uppercase',
                  color:'#8b8070',marginBottom:4})}>
                  {L.name} · {L.iso} · {L.guthrie} · Interactive Paradigm
                </div>
                <div style={{ fontFamily:T.serif, fontSize:38, color:T.cream,
                  letterSpacing:'-0.02em', lineHeight:1 }}>
                  –{root||'bona'}–
                </div>
                <div style={ss({fontSize:12,color:T.dusk,fontStyle:'italic',marginTop:4})}>
                  {gloss}
                </div>
              </div>
              <div style={{ textAlign:'right' }}>
                <div style={ss({fontSize:9,color:'#7a6a58',letterSpacing:'0.1em',
                  textTransform:'uppercase'})}>Gobelo Platform</div>
                <div style={sm({fontSize:8,color:L.color,marginTop:2})}>
                  gobelo.zambantutools.org
                </div>
              </div>
            </div>

            {/* Morpheme key */}
            <div style={{ background:'#f8f5f0', borderBottom:`1px solid ${T.rule}`,
              padding:'8px 24px', display:'flex', alignItems:'center',
              gap:0, flexWrap:'wrap' }}>
              {[
                ...( G.neg_type==='pre' && G.neg_pre
                  ? [{l:'neg. pre-initial',v:G.neg_pre+'-',dim:true}] : [] ),
                {l:'subj. concord',v:'SC-'},
                ...( G.neg_type==='infix' && G.neg_infix
                  ? [{l:'neg. infix',v:'-'+G.neg_infix+'-',dim:true}] : [] ),
                {l:'TAM marker',v:(active[0]&&G.tam[active[0]]?.mk)||'∅'},
                {l:'verb root',v:'-'+(root||'bona')+'-',brand:true},
                {l:'final vowel',v:'-'+(active[0]&&G.tam[active[0]]?.fv)||'a'},
              ].map((s,i,arr)=>(
                <span key={i} style={{ display:'flex',alignItems:'center' }}>
                  <span style={{ textAlign:'center',padding:'0 8px',
                    borderRight:`1px solid ${T.rule}` }}>
                    <span style={ss({fontSize:7,letterSpacing:'0.1em',textTransform:'uppercase',
                      color:T.sub,display:'block',marginBottom:1})}>{s.l}</span>
                    <span style={sm({fontSize:11,fontWeight:600,
                      color:s.brand?T.amber:s.dim?T.rule:T.soil})}>{s.v}</span>
                  </span>
                  {i<arr.length-1 && <span style={sm({fontSize:11,color:T.rule,padding:'0 2px'})}>+</span>}
                </span>
              ))}
            </div>

            {/* The table */}
            <div style={{ overflowX:'auto' }}>
              <table style={{ width:'100%', borderCollapse:'collapse',
                fontFamily:T.sans }}>
                <thead>
                  <tr style={{ background:T.soil }}>
                    <th style={{ padding:'8px 16px 8px 24px', textAlign:'left',
                      fontSize:8, letterSpacing:'0.12em', textTransform:'uppercase',
                      color:'#7a6a58', fontWeight:600, minWidth:110,
                      borderBottom:`2px solid ${T.bark}` }}>
                      Class · Person
                    </th>
                    {active.map((tid,i)=>{
                      const t = G.tam[tid];
                      const bl = i>0 ? `border-left:1.5px solid ${T.bark}` : '';
                      return showNeg
                        ? <th key={tid} colSpan={2} style={{
                            padding:'8px 6px', textAlign:'center', fontSize:9,
                            letterSpacing:'0.1em', textTransform:'uppercase',
                            color:T.cream, fontWeight:600,
                            borderBottom:`2px solid ${T.bark}`,
                            borderLeft: i>0?`1.5px solid ${T.bark}`:'none',
                          }}>{t.l}</th>
                        : <th key={tid} style={{
                            padding:'8px 6px', textAlign:'center', fontSize:9,
                            letterSpacing:'0.1em', textTransform:'uppercase',
                            color:T.cream, fontWeight:600,
                            borderBottom:`2px solid ${T.bark}`,
                            borderLeft: i>0?`1.5px solid ${T.bark}`:'none',
                          }}>{t.l}</th>;
                    })}
                  </tr>
                  {showNeg && (
                    <tr style={{ background:'#f8f5f0' }}>
                      <td style={{ padding:'3px 16px 5px 24px',
                        borderBottom:`1.5px solid ${T.soil}` }}></td>
                      {active.map((tid,i)=>(
                        <>
                          <td key={tid+'p'} style={{
                            fontSize:7,letterSpacing:'0.1em',textTransform:'uppercase',
                            color:T.dusk,textAlign:'center',padding:'3px 5px 5px',
                            borderBottom:`1.5px solid ${T.soil}`,
                            borderLeft:i>0?`1.5px solid ${T.rule}`:'none',
                          }}>affirm.</td>
                          <td key={tid+'n'} style={{
                            fontSize:7,letterSpacing:'0.1em',textTransform:'uppercase',
                            color:T.rule,textAlign:'center',padding:'3px 5px 5px',
                            borderBottom:`1.5px solid ${T.soil}`,
                          }}>negative</td>
                        </>
                      ))}
                    </tr>
                  )}
                </thead>
                <tbody>
                  {groups.map((grp,gi)=>{
                    const gc = groupColors[gi] || groupColors[1];
                    const showGroup = gi < 2 || showLoc;
                    if (!showGroup) return null;
                    return (
                      <>
                        <tr key={`gh-${gi}`} style={{ background:T.soil }}>
                          <td colSpan={1+nCols} style={{
                            fontSize:7,fontWeight:700,letterSpacing:'0.16em',
                            textTransform:'uppercase',color:'#8b8070',
                            padding:'4px 24px',
                          }}>{gc.label}</td>
                        </tr>
                        {grp.map(sc=>{
                          const isHL = highlight === sc.id;
                          return (
                            <tr key={sc.id}
                              onMouseEnter={()=>setHighlight(sc.id)}
                              onMouseLeave={()=>setHighlight(null)}
                              style={{ background: isHL?L.color+'0d':gc.bg,
                                cursor:'default', transition:'background 0.1s' }}>
                              <td style={{ padding:'5px 16px 5px 24px',
                                borderBottom:`0.5px solid ${T.rule}` }}>
                                <span style={sm({fontSize:10,fontWeight:700,
                                  color:T.soil,display:'block'})}>{sc.l}</span>
                                <span style={ss({fontSize:8,color:T.sub,
                                  display:'block',lineHeight:1.3})}>{sc.s}</span>
                              </td>
                              {active.map((tid,ti)=>{
                                const pos = getForm(sc, tid, false);
                                const neg = showNeg ? getForm(sc, tid, true) : null;
                                return (
                                  <>
                                    <td key={tid+'p'} style={{
                                      textAlign:'center',padding:'5px 6px',
                                      borderBottom:`0.5px solid ${T.rule}`,
                                      borderLeft:ti>0?`1.5px solid ${T.rule}`:'none',
                                      fontFamily:T.mono,fontSize:12,fontWeight:600,
                                      color:isHL?L.color:T.soil,
                                    }}>{pos}</td>
                                    {showNeg && (
                                      <td key={tid+'n'} style={{
                                        textAlign:'center',padding:'5px 5px',
                                        borderBottom:`0.5px solid ${T.rule}`,
                                        fontFamily:T.mono,fontSize:11,color:T.sub,
                                      }}>{neg}</td>
                                    )}
                                  </>
                                );
                              })}
                            </tr>
                          );
                        })}
                      </>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* Legend + formula */}
            <div style={{ padding:'8px 24px', background:'#f8f5f0',
              borderTop:`0.5px solid ${T.rule}`,
              display:'flex', gap:16, alignItems:'center', flexWrap:'wrap' }}>
              {[['#fffbf3','Human / personal'],['#f4f9f5','Noun classes'],
                ...(showLoc?[['#f4f4fb','Locative']]:[])
              ].map(([bg,l])=>(
                <div key={l} style={{ display:'flex',alignItems:'center',gap:5 }}>
                  <div style={{ width:14,height:8,borderRadius:1,background:bg,
                    border:`0.5px solid ${T.rule}`,flexShrink:0 }}/>
                  <span style={ss({fontSize:9,color:T.sub})}>{l}</span>
                </div>
              ))}
              <div style={{ marginLeft:'auto', fontFamily:T.mono, fontSize:8, color:T.sub }}>
                SC + TAM + ROOT + FV
                {showNeg && ` · NEG: ${G.neg_type==='infix'?`SC + -${G.neg_infix}- + ROOT`:`${G.neg_pre}- + SC + ROOT`} + NEG.FV`}
              </div>
            </div>

            {/* Footer */}
            <div style={{ padding:'8px 24px', display:'flex',
              justifyContent:'space-between', alignItems:'center',
              borderTop:`2px solid ${T.soil}`, background:T.soil }}>
              <div style={ss({fontSize:8,color:'#7a6a58',lineHeight:1.6})}>
                <span style={{ color:T.cream,fontWeight:600 }}>Zambia Languages Toolkit · Gobelo Platform</span><br/>
                Interactive Paradigm Explorer — gobelo.zambantutools.org
              </div>
              <div style={ss({fontSize:8,color:'#7a6a58',textAlign:'right',lineHeight:1.6})}>
                GGT {L.name} v1.0<br/>
                Hover rows to highlight · Free for educational use
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// ROOT
// ═══════════════════════════════════════════════════════════════════════════════
export default function GobелоPlatform() {
  const [tab, setTab] = useState('wotd');
  return (
    <div style={{ minHeight:'100vh', background:T.mist }}>
      <Nav tab={tab} setTab={setTab}/>
      {tab==='wotd'     && <WordOfTheDay/>}
      {tab==='paradigm' && <ParadigmExplorer/>}
    </div>
  );
}
