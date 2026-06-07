# GGTK Naming Decision - Visual Summary

**Quick Reference Guide**  
**Date:** June 7, 2026

---

## The Question

```
Should we rename:
  GGTK (Gobelo Grammar Toolkit)
      ↓
  ZLTK (Zambia Languages Toolkit)?
```

---

## The Answer: NO ❌

### Keep GGTK + Add "Gobelo" Branding ✅

---

## Side-by-Side Comparison

### Option A: Rename to ZLTK ❌

```
BEFORE                          AFTER (Broken)
────────                        ──────────────
from ggtk import *     →       from zltk import *
pip install ggtk       →       pip install zltk
ggtk analyze ...       →       zltk analyze ...
docs/ggtk_guide.md    →       docs/zltk_guide.md (rewrite everything!)

IMPACT:
❌ All code breaks
❌ All docs obsolete
❌ Users confused
❌ 40-80 hours migration
❌ Lost brand recognition
❌ SEO rankings drop
```

### Option B: Dual Branding ✅

```
TECHNICAL LAYER (Unchanged)   USER-FACING LAYER (New)
─────────────────────────     ───────────────────────
from ggtk import *            📱 Mobile App: "Gobelo Languages"
pip install ggtk              🌐 Website: gobelo.org
ggtk CLI tool                 📚 Marketing: "Zambian Languages NLP"
GitHub: gobelo/ggtk           🎯 Tagline: "Speak Zambian. Think Global."

IMPACT:
✅ Zero breaking changes
✅ Clear audience targeting
✅ Flexible positioning
✅ No migration needed
✅ Preserves technical credibility
✅ Enables consumer appeal
```

---

## How It Works in Practice

### For a Developer 💻

```python
# Install
pip install ggtk

# Import
from ggtk import GobeloGrammarLoader, GrammarConfig
from ggtk.apps.morphological_analyzer import MorphologicalAnalyzer

# Use
loader = GobeloGrammarLoader(GrammarConfig(language="toi"))
analyzer = MorphologicalAnalyzer(loader)
result = analyzer.analyze("balya")

print(result.best.segmented)  # ba-ly-a
```

**Experience:** Clean, technical, precise ✅

---

### For a Mobile User 📱

```
App Store Listing:

╔═══════════════════════════════════╗
║  Gobelo Languages                 ║
║  Learn Zambian Languages with AI  ║
║                                   ║
║  ⭐⭐⭐⭐⭐ 4.8 (2.3K reviews)     ║
║                                   ║
║  🇿🇲 Master chiTonga, chiBemba,   ║
║     Nyanja & 4 more languages     ║
║                                   ║
║  ✓ AI-powered lessons             ║
║  ✓ Pronunciation coach            ║
║  ✓ Cultural insights              ║
║  ✓ Offline mode                   ║
║                                   ║
║  [GET] [Free Trial]               ║
╚═══════════════════════════════════╝

Powered by GGTK (in small print at bottom)
```

**Experience:** Friendly, accessible, engaging ✅

---

### For a Researcher 🔬

```
Academic Paper Citation:

"We analyzed morphological patterns using the 
Gobelo Grammar Toolkit (GGTK v1.0), a grammar-driven 
NLP engine for Zambian Bantu languages (Habeenzu et al., 
2026). GGTK provides structured morphological analysis 
through a YAML-based grammar representation..."

Technical Documentation:
https://github.com/gobelo/gobelo-grammar-toolkit
```

**Experience:** Credible, citable, rigorous ✅

---

### For a Student 🎓

```
Website Landing Page (gobelo.org):

╔══════════════════════════════════════════╗
║                                          ║
║   Speak Zambian. Think Global. 🌍        ║
║                                          ║
║   Learn 7 official Zambian languages     ║
║   with AI-powered tools                  ║
║                                          ║
║   [Start Learning] [For Teachers]        ║
║                                          ║
║   ┌────────┬────────┬────────┐          ║
║   │chiTonga│chiBemba│ Nyanja │          ║
║   │ siLozi │ Luvale │ Lunda  │          ║
║   │ Kaonde │        │        │          ║
║   └────────┴────────┴────────┘          ║
║                                          ║
║   Powered by GGTK                        ║
║   (Gobelo Grammar Toolkit)               ║
║                                          ║
╚══════════════════════════════════════════╝
```

**Experience:** Inspiring, clear, motivating ✅

---

## Real-World Analogies

This dual branding strategy is proven:

```
TensorFlow (technical)         GGTK (technical)
    ↓                              ↓
TensorFlow Lite (mobile)     Gobelo Languages (mobile)
TF.js (web)                  Gobelo.org (web)
TFX (production)             Gobelo Classroom (education)


Linux (kernel)               GGTK (engine)
    ↓                              ↓
Ubuntu (desktop)             Gobelo Languages (app)
Red Hat (enterprise)         Gobelo Enterprise (B2B)
Android (mobile)             Gobelo Mobile (future)


React (library)              GGTK (library)
    ↓                              ↓
React Native (mobile)        Gobelo Languages (mobile)
Next.js (framework)          Gobelo Platform (web)
Gatsby (static sites)        Gobelo Docs (documentation)
```

**Pattern:** Strong technical foundation → Multiple user-facing products

---

## Decision Tree

```
User asks: "What should I use?"
         │
         ├─ Are you a developer/researcher?
         │   └─ YES → Use GGTK
         │           ├─ pip install ggtk
         │           ├─ from ggtk import ...
         │           └─ Read technical docs
         │
         ├─ Are you a student/learner?
         │   └─ YES → Use Gobelo Languages
         │           ├─ Download mobile app
         │           ├─ Take interactive lessons
         │           └─ Practice with AI
         │
         ├─ Are you a teacher?
         │   └─ YES → Use Gobelo Classroom
         │           ├─ Create lessons
         │           ├─ Track students
         │           └─ Access resources
         │
         └─ Are you curious about Zambia?
             └─ YES → Visit gobelo.org
                     ├─ Explore cultures
                     ├─ Learn basics
                     └─ Join community
```

**Everyone finds what they need!** ✅

---

## Migration Cost Comparison

### Renaming to ZLTK

```
Task                          Hours    Risk
──────────────────────────    ─────    ────
Update all imports            8        HIGH
Rewrite documentation         16       HIGH
Update tests                  4        MEDIUM
Change PyPI package           2        HIGH
Rename GitHub repo            1        MEDIUM
Update CI/CD pipelines        4        MEDIUM
Communicate to users          8        HIGH
Support transition            12       HIGH
Fix broken external links     8        MEDIUM
Update marketing materials    4        LOW
                              ─────
Total:                        67 hours
Risk Level:                   ⚠️⚠️⚠️ VERY HIGH
```

### Dual Branding (GGTK + Gobelo)

```
Task                          Hours    Risk
──────────────────────────    ─────    ────
Update README.md              1        NONE
Create branding docs          4        NONE
Design mobile app concept     8        NONE
Register domain               1        NONE
Build landing page            16       LOW
Create social media           2        NONE
Write blog post               4        NONE
                              ─────
Total:                        36 hours
Risk Level:                   ✅ LOW
```

**Savings:** 31 hours + zero breaking changes!

---

## Audience Mapping

```
AUDIENCE              USES                NAME PREFERENCE
──────────────        ────────────        ───────────────
Python developers     ggtk package        GGTK ✅
Linguists             ggtk API            Gobelo Grammar Toolkit ✅
Researchers           ggtk data           GGTK ✅
Mobile users          Gobelo app          Gobelo Languages ✅
Students              Gobelo web          Gobelo ✅
Teachers              Gobelo Classroom    Gobelo Education ✅
Press/Media           Press releases      Gobelo ✅
Government            Partnerships        Gobelo/GGTK (both) ✅
Investors             Pitch decks         Gobelo ✅
```

**Each audience gets the name that resonates with them!** ✅

---

## Brand Architecture

```
GOBELO (Master Brand)
    │
    ├─ GGTK (Technical Product)
    │   ├─ Python Package (pip install ggtk)
    │   ├─ REST API (web/backend)
    │   ├─ CLI Tool (ggtk command)
    │   └─ Research Tools
    │
    ├─ Gobelo Languages (Consumer Product)
    │   ├─ iOS App
    │   ├─ Android App
    │   ├─ Web Platform (gobelo.org)
    │   └─ Community Features
    │
    ├─ Gobelo Classroom (Education Product)
    │   ├─ Teacher Dashboard
    │   ├─ Student Portal
    │   ├─ Curriculum Builder
    │   └─ Assessment Tools
    │
    └─ Gobelo Enterprise (B2B Product)
        ├─ White-label Solutions
        ├─ Custom Language Packs
        ├─ API Licensing
        └─ Consulting Services
```

**One foundation, multiple products!** ✅

---

## Key Takeaways

### ✅ DO:
- Keep `ggtk` as package/technical name
- Use "Gobelo Languages" for mobile app
- Position differently per audience
- Maintain technical excellence
- Build consumer-friendly experiences

### ❌ DON'T:
- Rename package to `zltk`
- Break existing code
- Confuse current users
- Lose technical credibility
- Force migration on anyone

### 🎯 RESULT:
- Developers happy (clear API)
- Users happy (friendly app)
- Researchers happy (rigorous tools)
- Business happy (multiple revenue streams)
- Culture happy (languages preserved)

---

## One-Liner Explanations

**For different contexts:**

```
Elevator pitch:
"Gobelo makes Zambian languages accessible through AI"

Developer intro:
"GGTK is a grammar-driven NLP toolkit for Zambian Bantu languages"

App store description:
"Learn Zambian languages with Gobelo Languages"

Academic abstract:
"We present GGTK, a computational framework for Bantu morphology"

Investor deck:
"Gobelo is building the Duolingo for African languages"

Press release:
"New platform democratizes access to Zambian language learning"
```

**Same project, different angles!** ✅

---

## Final Verdict

```
╔════════════════════════════════════════════════════╗
║                                                    ║
║   KEEP GGTK ✅                                     ║
║   ADD GOBELO BRANDING ✅                           ║
║   DON'T RENAME TO ZLTK ❌                          ║
║                                                    ║
║   Best of both worlds:                             ║
║   • Technical precision (GGTK)                     ║
║   • Mass market appeal (Gobelo)                    ║
║   • Zero breaking changes                          ║
║   • Maximum flexibility                            ║
║                                                    ║
║   "GGTK is the engine. Gobelo is the experience."  ║
║                                                    ║
╚════════════════════════════════════════════════════╝
```

---

**Decision Made:** June 7, 2026  
**Implementation Status:** ✅ Complete  
**Next Steps:** Execute branding rollout (see BRANDING_STRATEGY.md)

---

## Quick Links

- 📖 Full Strategy: [`docs/BRANDING_STRATEGY.md`](docs/BRANDING_STRATEGY.md)
- 📱 Mobile Concept: [`docs/MOBILE_APP_CONCEPT.md`](docs/MOBILE_APP_CONCEPT.md)
- 📝 Decision Details: [`docs/NAMING_DECISION.md`](docs/NAMING_DECISION.md)
- 🚀 Enhancements: [`ENHANCEMENT_AUDIT_SUMMARY.md`](../ENHANCEMENT_AUDIT_SUMMARY.md)
