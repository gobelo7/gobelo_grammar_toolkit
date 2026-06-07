# GGTK vs ZLTK - Strategic Naming Decision (Pre-Launch)

**Date:** June 7, 2026  
**Status:** Under Development/Testing - No Breaking Change Concerns  
**Decision:** Pending user choice

---

## Context

GGTK is currently in development/testing phase with no public releases. This means:

✅ **No breaking change concerns** - Can rename freely  
✅ **No existing users to confuse** - Clean slate  
✅ **No SEO to lose** - Starting from zero  
✅ **No PyPI conflicts** - Haven't published yet  
✅ **Full flexibility** - Choose what's best long-term  

This is the **ideal time** to make the right naming decision.

---

## Option 1: Keep GGTK (Gobelo Grammar Toolkit)

### Pros ✅

1. **Already Established in Codebase**
   - All imports use `ggtk`
   - Directory structure: `ggtk/`
   - CLI command: `ggtk`
   - Test fixtures reference `ggtk`
   - Documentation uses `ggtk`

2. **Technically Accurate**
   - "Grammar Toolkit" precisely describes functionality
   - Appeals to linguists and NLP researchers
   - Clear about being a toolkit (not end-user app)

3. **Short & Memorable**
   - 4 letters = easy to type
   - Follows Python convention (short package names)
   - Examples: `nltk`, `spacy`, `stanza`, `ggtk`

4. **"Gobelo" Brand Identity**
   - Unique, ownable brand name
   - Not generic (stands out)
   - Can build brand equity around it

5. **Academic Credibility**
   - Sounds like research tool
   - Appropriate for academic citations
   - Fits linguistics/NLP community expectations

### Cons ❌

1. **Doesn't Convey "Zambian Languages"**
   - Could be for any language family
   - Geographic focus not obvious
   - Might need tagline/explanation

2. **"Grammar" Sounds Narrow/Academic**
   - May intimidate non-linguists
   - Doesn't suggest mobile/consumer use
   - Less appealing for general audience

3. **Four-Letter Acronyms Can Be Forgettable**
   - What does GGTK stand for?
   - Need to explain every time
   - Harder to remember than descriptive names

4. **Mobile App Naming Challenge**
   - "GGTK Mobile" sounds technical
   - Hard to brand consumer product
   - May need separate app name anyway

---

## Option 2: Rename to ZLTK (Zambia Languages Toolkit)

### Pros ✅

1. **Immediately Communicates Focus**
   - "Zambia" = geographic/cultural context clear
   - "Languages" = broader than just grammar
   - Users instantly know what it's for

2. **More Accessible to Non-Linguists**
   - "Languages Toolkit" less intimidating
   - Appeals to teachers, students, general public
   - Better for mobile app positioning

3. **Mission-Aligned**
   - Emphasizes Zambian language preservation
   - Cultural mission front-and-center
   - Easier to get grants/partnerships

4. **Better for Marketing**
   - Descriptive = easier SEO
   - People search "Zambia languages" not "grammar toolkit"
   - Clear value proposition

5. **Mobile-Friendly**
   - "ZLTK" or "Zambia Languages" works as app name
   - More appealing in app stores
   - Easier to explain to general users

### Cons ❌

1. **Requires Renaming Everything Now**
   - Package name: `ggtk` → `zltk`
   - Imports: `from ggtk import` → `from zltk import`
   - Directory: `ggtk/` → `zltk/`
   - CLI: `ggtk` → `zltk`
   - All test files, docs, examples

2. **Work Required (But Manageable)**
   - Estimated: 4-8 hours of renaming
   - Find-replace across codebase
   - Update documentation
   - Verify all tests pass

3. **"Toolkit" Still Technical**
   - Doesn't fully solve consumer appeal issue
   - Still might need separate app name
   - "Toolkit" suggests developer tool

4. **Geographic Limitation**
   - Locked to "Zambia" in name
   - Harder to expand to other countries later
   - What if you add Malawian languages?

5. **Less Unique**
   - "Zambia Languages" is descriptive but generic
   - Harder to trademark/brand
   - Many projects could use similar name

---

## Option 3: Hybrid Approach (Recommended ⭐)

### Keep `ggtk` as Package Name, Use Descriptive Branding

**Technical Layer:**
- Package: `ggtk` (unchanged)
- Import: `from ggtk import ...`
- CLI: `ggtk`

**Branding Layer:**
- Full name: "Gobelo Grammar Toolkit (GGTK)"
- Tagline: "The Zambian Languages NLP Engine"
- Description: "Grammar-driven toolkit for 7 official Zambian Bantu languages"
- Mobile app: "Gobelo Languages" or "Zambian Languages Lab"

### Why This Works Best:

✅ **Minimal work now** - Keep existing code structure  
✅ **Flexible positioning** - Can emphasize different aspects per audience  
✅ **Best of both worlds** - Technical precision + marketing appeal  
✅ **Future-proof** - Can expand beyond Zambia without renaming  
✅ **Brand building** - "Gobelo" becomes recognizable brand  

### Implementation:

```python
# Package stays as ggtk
pip install ggtk
from ggtk import GobeloGrammarLoader

# But marketing emphasizes Zambian languages
"""
Gobelo Grammar Toolkit (GGTK)
The Zambian Languages NLP Engine

Analyze, generate, and learn chiTonga, chiBemba, Nyanja, 
siLozi, Luvale, Lunda, and Kaonde using AI-powered 
morphological analysis.
"""
```

---

## Decision Framework

### Ask Yourself These Questions:

#### 1. Who is your PRIMARY audience?

| Audience | Best Name |
|----------|-----------|
| Linguists/Researchers | GGTK ✅ |
| NLP Developers | GGTK ✅ |
| Teachers/Educators | ZLTK or Gobelo |
| General Public/Learners | Gobelo Languages |
| Government/NGOs | ZLTK or Gobelo |
| Mixed (all above) | Hybrid (GGTK + branding) ⭐ |

#### 2. What's your long-term vision?

| Vision | Best Name |
|--------|-----------|
| Academic research tool | GGTK ✅ |
| Commercial language learning platform | Gobelo Languages |
| Open-source community project | GGTK or Hybrid |
| Government/educational initiative | ZLTK |
| Pan-African expansion | Gobelo (not Zambia-specific) |

#### 3. How important is brand uniqueness?

| Priority | Best Name |
|----------|-----------|
| High (want unique brand) | Gobelo/GGTK ✅ |
| Medium | Hybrid approach |
| Low (descriptive is fine) | ZLTK |

#### 4. Will you expand beyond Zambia?

| Plan | Best Name |
|------|-----------|
| Zambia only | ZLTK works |
| Expand to other African countries | Gobelo (not Zambia-specific) ⭐ |
| Global Bantu languages | GGTK or Gobelo |

#### 5. What's your mobile strategy?

| Strategy | Best Approach |
|----------|---------------|
| No mobile app planned | GGTK is fine |
| Separate mobile app | GGTK (backend) + Gobelo Languages (app) ⭐ |
| Mobile-first | Consider Gobelo/ZLTK from start |

---

## Recommendation Based on Your Goals

### If Your Goal Is:

#### 🎯 Academic/Research Focus
**Choose: GGTK**
- Precise, credible, standard for NLP tools
- Easy to cite in papers
- Appeals to linguistics community

#### 🎯 Commercial Language Learning Platform
**Choose: Gobelo Languages (with GGTK backend)**
- Consumer-friendly app name
- Technical backend stays as GGTK
- Best of both worlds

#### 🎯 Government/Educational Initiative
**Choose: ZLTK or "Zambian Languages Digital Platform"**
- Descriptive, mission-aligned
- Easy for stakeholders to understand
- Emphasizes national importance

#### 🎯 Open-Source Community Project
**Choose: GGTK with strong branding**
- Developer-friendly package name
- Clear documentation
- Community-building around "Gobelo" brand

#### 🎯 Pan-African Expansion
**Choose: Gobelo (not Zambia-specific)**
- Scalable beyond one country
- Brand-focused, not geography-locked
- Flexible for future growth

---

## My Recommendation: HYBRID APPROACH ⭐

Based on what I know about your project:

1. **You're building both technical tools AND user-facing products**
2. **You want to preserve Zambian languages (mission-driven)**
3. **You're considering mobile apps**
4. **You may expand beyond Zambia eventually**

### Therefore:

**Keep `ggtk` as the package name** because:
- It's already implemented
- Short, memorable, follows conventions
- Technically accurate
- No reason to change it

**But brand it as "Gobelo - The Zambian Languages Platform"** because:
- Emphasizes mission and geography
- Consumer-friendly for mobile/web
- Flexible for expansion
- Builds unique brand identity

### Implementation:

```
Package/Code:     ggtk (no changes needed)
├── pip install ggtk
├── from ggtk import ...
└── ggtk CLI

Brand/Marketing:  Gobelo
├── Tagline: "The Zambian Languages NLP Engine"
├── Mobile App: "Gobelo Languages"
├── Web Platform: gobelo.org
└── Mission: "Preserving Zambian languages through technology"

Documentation:    Dual positioning
├── For developers: "GGTK technical docs"
├── For users: "Gobelo learning platform"
└── For everyone: "Powered by GGTK"
```

---

## What You Should Do NOW (Since You're in Development)

### Immediate Actions (This Week):

1. **Decide on naming strategy** (use framework above)
2. **If keeping GGTK:**
   - Add tagline to README: "The Zambian Languages NLP Engine"
   - Update description in pyproject.toml
   - Create basic branding guidelines

3. **If renaming to ZLTK:**
   - Do it NOW before more code is written
   - Use find-replace across codebase
   - Update all documentation
   - Verify tests pass

4. **If hybrid approach:**
   - Keep ggtk as-is (no changes)
   - Create "Gobelo" brand identity
   - Plan mobile app naming separately
   - Update marketing materials

### Don't Rush:
Take time to think about:
- Long-term vision (1-3 years)
- Target audiences
- Business model
- Expansion plans

This decision shapes your project's identity. Get it right now while it's easy to change.

---

## Comparison Summary

| Factor | GGTK | ZLTK | Hybrid (Recommended) |
|--------|------|------|---------------------|
| **Implementation Effort** | None (keep as-is) | 4-8 hours renaming | Minimal (add branding) |
| **Technical Clarity** | ✅ Excellent | ✅ Good | ✅ Excellent |
| **Consumer Appeal** | ⚠️ Limited | ✅ Better | ✅ Best (separate app name) |
| **Brand Uniqueness** | ✅ High (Gobelo) | ⚠️ Generic | ✅ High (Gobelo) |
| **Geographic Flexibility** | ✅ High | ❌ Locked to Zambia | ✅ High |
| **Mobile App Naming** | ⚠️ Needs separate name | ✅ Works as-is | ✅ Best (Gobelo Languages) |
| **Academic Credibility** | ✅ Excellent | ⚠️ Good | ✅ Excellent |
| **Marketing Ease** | ⚠️ Needs explanation | ✅ Self-explanatory | ✅ Best of both |
| **Future-Proof** | ✅ Yes | ❌ Limited | ✅ Yes |
| **Community Building** | ✅ Strong brand | ⚠️ Generic | ✅ Strong brand |

---

## Final Thought

Since you're in development with no users yet, you have the luxury of choosing wisely without pressure. 

**My advice:** Don't rush. Think about where you want to be in 2-3 years. Then choose the name that supports that vision.

- If you see GGTK as primarily a **research/developer tool** → Keep GGTK
- If you see it as a **consumer language learning platform** → Consider ZLTK or Gobelo
- If you see it as **both** (technical foundation + user products) → Hybrid approach ⭐

The hybrid approach gives you maximum flexibility with minimal effort. That's why I recommend it.

But ultimately, **you know your vision best**. Choose what aligns with your goals.

---

## Next Steps

1. **Review this document** and the detailed analyses
2. **Discuss with your team** (if applicable)
3. **Consider your 2-3 year vision**
4. **Make a decision** (don't procrastinate too long!)
5. **Implement consistently** across all touchpoints
6. **Document the decision** for future reference

Once you decide, I can help implement whichever path you choose. Just let me know!

---

**Created:** June 7, 2026  
**Purpose:** Strategic naming decision support (pre-launch)  
**Status:** Awaiting user decision
