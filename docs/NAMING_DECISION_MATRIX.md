# Quick Naming Decision Matrix

**GGTK vs ZLTK - Pre-Launch Decision Tool**  
**Date:** June 7, 2026

---

## Answer These 5 Questions

Rate each statement 1-5 (1 = Strongly Disagree, 5 = Strongly Agree)

### Question 1: Primary Audience
```
"My primary users are developers/researchers, not general public"

Score: ___ / 5

If 4-5 → Lean toward GGTK
If 1-3 → Lean toward ZLTK or Gobelo
```

### Question 2: Mobile Strategy
```
"I plan to launch a consumer mobile app within 12 months"

Score: ___ / 5

If 4-5 → Consider separate app name (Gobelo Languages)
If 1-3 → GGTK or ZLTK both work
```

### Question 3: Geographic Scope
```
"I want to expand beyond Zambia to other African countries"

Score: ___ / 5

If 4-5 → Avoid "Zambia" in name (choose GGTK or Gobelo)
If 1-3 → ZLTK works fine
```

### Question 4: Brand Importance
```
"Building a unique, recognizable brand is important to me"

Score: ___ / 5

If 4-5 → Choose Gobelo/GGTK (unique brand)
If 1-3 → ZLTK (descriptive) is fine
```

### Question 5: Commercial Intent
```
"I plan to monetize this as a commercial product"

Score: ___ / 5

If 4-5 → Hybrid approach (GGTK backend + Gobelo brand)
If 1-3 → GGTK (open-source focus) works
```

---

## Scoring Guide

### If You Scored Mostly 4-5 on Questions:

**Q1 High + Q2 Low + Q3 High + Q4 High + Q5 Low**
→ **Keep GGTK** ✅
- Academic/research focus
- No immediate mobile plans
- Want flexibility for expansion
- Value unique branding
- Open-source/community driven

**Action:** Keep `ggtk` as-is, add tagline emphasizing Zambian languages

---

**Q1 Low + Q2 High + Q3 Low + Q4 Medium + Q5 High**
→ **Consider ZLTK or Gobelo** 
- Consumer/education focus
- Mobile app planned
- Zambia-specific mission
- Descriptive naming preferred
- Commercial intent

**Action:** Rename to `zltk` now (easy while in development) OR use hybrid approach

---

**Mixed Scores (Some High, Some Low)**
→ **Hybrid Approach Recommended** ⭐
- Serving multiple audiences
- Both technical and consumer products
- Want flexibility
- Building brand while maintaining technical credibility

**Action:** Keep `ggtk` package, create "Gobelo" brand for user-facing products

---

## Simple Decision Tree

```
Start
  │
  ├─ Is your PRIMARY audience developers/researchers?
  │   ├─ YES → Keep GGTK ✅
  │   └─ NO ↓
  │
  ├─ Are you building a consumer mobile app?
  │   ├─ YES → Use Hybrid (ggtk backend + Gobelo app) ⭐
  │   └─ NO ↓
  │
  ├─ Will you expand beyond Zambia?
  │   ├─ YES → Keep GGTK or use Gobelo (not Zambia-specific)
  │   └─ NO ↓
  │
  ├─ Is descriptive naming important (SEO, clarity)?
  │   ├─ YES → Consider ZLTK
  │   └─ NO ↓
  │
  └─ Default Recommendation: Keep GGTK with better branding ✅
```

---

## Three Clear Paths

### Path A: Keep GGTK (Simplest) ✅

**Best if:**
- Primary audience is developers/researchers
- Academic credibility important
- Want minimal changes
- May expand beyond Zambia

**Actions:**
1. Keep all code as `ggtk`
2. Add tagline: "The Zambian Languages NLP Engine"
3. Update README to emphasize Zambian focus
4. Done! (30 minutes of work)

**Pros:** Zero disruption, technically accurate, flexible  
**Cons:** Less obvious consumer appeal

---

### Path B: Rename to ZLTK (Descriptive)

**Best if:**
- Primary audience is educators/students/general public
- Zambia-specific mission is core identity
- Don't plan to expand geographically
- Want self-explanatory name

**Actions:**
1. Rename directory: `ggtk/` → `zltk/`
2. Find-replace all imports: `from ggtk` → `from zltk`
3. Update CLI entry point in pyproject.toml
4. Update all documentation
5. Run tests to verify everything works
6. Commit changes

**Estimated Time:** 4-8 hours  
**Risk:** Low (no users yet)

**Pros:** Immediately clear purpose, better for non-technical users  
**Cons:** Locked to Zambia, less unique brand

---

### Path C: Hybrid Approach (Most Flexible) ⭐ RECOMMENDED

**Best if:**
- Serving multiple audiences (developers + end users)
- Planning mobile app + technical tools
- Want to build unique brand
- May expand beyond Zambia

**Actions:**
1. Keep `ggtk` package unchanged
2. Create "Gobelo" brand identity
3. Position GGTK as "engine" behind Gobelo products
4. Plan mobile app as "Gobelo Languages"
5. Update marketing materials with dual positioning

**Estimated Time:** 2-4 hours (mostly documentation/branding)  
**Risk:** None (no breaking changes)

**Pros:** Best of both worlds, maximum flexibility, proven strategy  
**Cons:** Slightly more complex messaging (mitigated by good docs)

---

## My Recommendation Based on Your Project

Looking at what you've built:

✅ Comprehensive NLP toolkit (technical)  
✅ Web backend API (developer-focused)  
✅ Considering mobile app (consumer-focused)  
✅ Mission-driven (preserve Zambian languages)  
✅ Still in development (flexible)  

**This suggests: HYBRID APPROACH** ⭐

### Why:
1. You're building BOTH technical tools AND user products
2. You need credibility with researchers AND appeal to learners
3. You may expand beyond Zambia eventually
4. You're still in development (easy to implement now)

### Implementation:
```
Technical Layer:     ggtk (keep as-is)
├── Package name
├── Import path
├── CLI command
└── Developer API

Brand Layer:         Gobelo (add this)
├── Tagline: "The Zambian Languages NLP Engine"
├── Mobile app: "Gobelo Languages"
├── Website: gobelo.org
└── Marketing message

Result:              Best of both worlds ✅
```

---

## What NOT to Do

❌ **Don't procrastinate** - Decide soon while codebase is small  
❌ **Don't overthink** - All three options can work  
❌ **Don't worry about perfection** - Can adjust branding later  
❌ **Don't rename just for renaming's sake** - Have clear reason  

✅ **DO decide based on your vision**  
✅ **DO consider your primary audience**  
✅ **DO think 2-3 years ahead**  
✅ **DO document your decision**  

---

## Quick Comparison Table

| Criteria | GGTK | ZLTK | Hybrid |
|----------|------|------|--------|
| Implementation effort | None | 4-8 hours | 2-4 hours |
| Technical clarity | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Consumer appeal | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Brand uniqueness | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| Geographic flexibility | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| Mobile-friendly | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Academic credibility | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Future-proof | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| **Overall Score** | **Strong** | **Good** | **Best** ⭐ |

---

## Final Checklist

Before deciding, confirm:

- [ ] I understand my primary audience
- [ ] I have a 2-3 year vision
- [ ] I know if I'll expand beyond Zambia
- [ ] I've considered mobile strategy
- [ ] I've discussed with team (if applicable)
- [ ] I'm ready to commit to a decision

Once checked, choose your path and implement consistently!

---

## Need Help Deciding?

Ask yourself: **"In 3 years, what do I want this project to be known for?"**

- **"The best technical toolkit for Bantu NLP"** → GGTK
- **"The go-to platform for learning Zambian languages"** → Gobelo/Hybrid
- **"The national digital language initiative"** → ZLTK

Your answer reveals the right choice.

---

**Remember:** Since you're in development, you can't make a "wrong" choice. All three paths lead to success. The key is choosing intentionally and implementing consistently.

Take your time, think strategically, and choose what aligns with YOUR vision.

Good luck! 🚀
