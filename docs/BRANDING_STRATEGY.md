# GGTK Branding Strategy & Naming Recommendation

**Date:** June 7, 2026  
**Decision:** Maintain `ggtk` as technical name, adopt dual branding strategy

---

## Executive Summary

After careful consideration of the proposal to rename GGTK (Gobelo Grammar Toolkit) to ZLTK (Zambia Languages Toolkit), we recommend a **hybrid dual-branding approach**:

- **Keep `ggtk`** as the package name, import path, and technical identifier
- **Adopt "Zambian Languages Toolkit"** or **"Gobelo Languages"** for user-facing products (mobile app, web platform, marketing)

This strategy preserves technical stability while enabling broader market appeal.

---

## Analysis of Options

### Option 1: Keep GGTK (Recommended ✅)

**Technical Name:** `ggtk` / Gobelo Grammar Toolkit  
**User-Facing Name:** "Zambian Languages Toolkit by Gobelo" or "Gobelo Languages"

#### Advantages:
1. **Zero Breaking Changes** - No code modifications needed
2. **Preserves Investment** - All existing documentation, tutorials, and integrations remain valid
3. **Developer Clarity** - `ggtk` is short, memorable, and follows Python naming conventions
4. **Brand Continuity** - Maintains recognition in academic/research communities
5. **Flexibility** - Can position differently for different audiences

#### Disadvantages:
1. "Grammar Toolkit" may sound narrow/academic to general users
2. Doesn't immediately convey Zambian language focus

#### Mitigation:
- Use descriptive taglines in marketing materials
- Position mobile/web apps with user-friendly names
- Emphasize "7 Zambian Languages" in all user-facing content

---

### Option 2: Rename to ZLTK (Not Recommended ❌)

**Technical Name:** `zltk` / Zambia Languages Toolkit

#### Advantages:
1. Immediately communicates geographic focus
2. "Languages Toolkit" more accessible than "Grammar Toolkit"
3. Better for mass-market mobile app branding

#### Disadvantages:
1. **Catastrophic Breaking Changes:**
   - All imports break: `from ggtk import ...` → `from zltk import ...`
   - Package name change on PyPI (lose existing installs)
   - CLI command changes: `ggtk` → `zltk`
   - All documentation becomes obsolete
   - All tutorials, blog posts, StackOverflow answers become invalid
   - GitHub repository rename required

2. **Migration Nightmare:**
   ```python
   # Before (thousands of lines across projects)
   from ggtk import GobeloGrammarLoader, GrammarConfig
   from ggtk.apps.morphological_analyzer import MorphologicalAnalyzer
   
   # After (must update EVERYWHERE)
   from zltk import GobeloGrammarLoader, GrammarConfig
   from zltk.apps.morphological_analyzer import MorphologicalAnalyzer
   ```

3. **Confusion Period:**
   - Users won't know if `ggtk` and `zltk` are same project
   - Search results split between old and new names
   - Support burden increases dramatically

4. **Loss of Brand Equity:**
   - Any existing recognition of "GGTK" is lost
   - Academic citations become harder to find
   - SEO rankings drop during transition

5. **Technical Debt:**
   - Must maintain backward compatibility layer or force migration
   - Dual package support during transition (complex)
   - Risk of fragmenting community

#### Estimated Cost:
- **Development Time:** 40-80 hours (renaming, testing, documentation)
- **Community Impact:** High confusion, potential user loss
- **Risk Level:** ⚠️⚠️⚠️ Very High

---

## Recommended Strategy: Dual Branding ✅

### Technical Layer (Unchanged)
```
Package Name:     ggtk
Import Path:      from ggtk import ...
CLI Command:      ggtk analyze --lang toi "balya"
PyPI Package:     ggtk
GitHub Repo:      gobelo/gobelo-grammar-toolkit
Code Directory:   ggtk/
```

### User-Facing Layer (Rebranded)

#### Mobile App Options:
1. **"Gobelo Languages"** (Recommended)
   - Clean, modern, brandable
   - Works globally (not limited to Zambia perception)
   - Easy to remember

2. **"Zambian Languages Toolkit"**
   - Descriptive, clear purpose
   - May limit perceived scope outside Zambia

3. **"Bantu Languages Lab"**
   - Academic positioning
   - Appeals to researchers/students

#### Web Platform:
- **URL:** `gobelo.org` or `gobelolanguages.com`
- **Title:** "Gobelo - Learn Zambian Languages"
- **Subtitle:** "Powered by GGTK (Gobelo Grammar Toolkit)"

#### Documentation:
- **Main Title:** "Gobelo Grammar Toolkit (GGTK)"
- **Tagline:** "The Zambian Languages NLP Engine"
- **Description:** "Grammar-driven toolkit for 7 official Zambian Bantu languages"

#### Marketing Materials:
```
Headline: "Explore Zambian Languages with AI"
Subhead:  "Powered by GGTK - The Gobelo Grammar Toolkit"
Body:     "Analyze, generate, and learn chiTonga, chiBemba, 
           chiNyanja, siLozi, Luvale, Lunda, and Kaonde"
```

---

## Implementation Plan

### Phase 1: Update Documentation (Low Effort, High Impact)

#### 1. Update README.md
Add user-friendly positioning while keeping technical accuracy:

```markdown
# Gobelo Grammar Toolkit (GGTK)
## The Zambian Languages NLP Engine

A grammar-driven NLP library for the 7 official Zambian Bantu languages.

🌍 **For End Users:** Try our mobile app "Gobelo Languages"  
💻 **For Developers:** Use the `ggtk` Python package  
📚 **For Researchers:** Access linguistic data and analysis tools
```

#### 2. Create Landing Page Content
Position for different audiences:

```
For Students:
"Learn Zambian languages with interactive exercises powered by AI"

For Teachers:
"Create custom lessons and assessments for 7 Zambian languages"

For Developers:
"Build language apps with our Python toolkit and REST API"

For Linguists:
"Access structured grammatical data for Bantu languages"
```

#### 3. Update Web Backend README
Emphasize user-facing applications:

```markdown
# GGTK Web API
## Backend for Zambian Language Applications

RESTful API powering:
- 📱 Gobelo Languages mobile app
- 🌐 Gobelo web learning platform
- 🔬 Research and analysis tools
```

---

### Phase 2: Mobile App Branding

#### App Store Listing Example:

```
App Name: Gobelo Languages
Subtitle: Learn Zambian Languages with AI

Description:
Master chiTonga, chiBemba, chiNyanja, and 4 other Zambian 
languages with AI-powered exercises, pronunciation guides, 
and cultural insights.

Features:
✓ Interactive lessons for 7 Zambian languages
✓ AI pronunciation feedback
✓ Cultural context and proverbs
✓ Offline mode for rural areas
✓ Progress tracking and achievements

Powered by GGTK (Gobelo Grammar Toolkit) - 
The open-source NLP engine for Zambian languages.
```

#### App Icon/Logo:
- Keep "Gobelo" as primary brand
- Use colors/patterns inspired by Zambian culture
- Tagline: "Zambian Languages, Modern Technology"

---

### Phase 3: Marketing Materials

#### Website Copy:

**Homepage Headline Options:**
1. "Speak Zambian. Think Global."
2. "Your Gateway to Zambian Languages"
3. "AI-Powered Zambian Language Learning"

**Value Proposition:**
```
Traditional methods teach you words.
Gobelo teaches you the grammar, culture, and soul of Zambian languages.

Built on GGTK - the most comprehensive computational grammar 
of Zambian Bantu languages ever created.
```

**Target Audiences:**
- Diaspora reconnecting with heritage
- Students in Zambian schools
- Researchers in African linguistics
- Travelers and expats
- Language enthusiasts

---

### Phase 4: Community Building

#### Positioning Statements:

**For GitHub/Developers:**
> "GGTK is the leading open-source grammar-driven NLP toolkit for Zambian Bantu languages, providing morphological analysis, generation, and corpus annotation capabilities through a single YAML grammar source."

**For General Public:**
> "Gobelo makes Zambian languages accessible to everyone through AI-powered learning tools, built on decades of linguistic research."

**For Academia:**
> "The Gobelo Grammar Toolkit (GGTK) represents a paradigm shift in computational morphology for under-resourced languages, using a grammar-as-code approach to encode complex Bantu morphosyntactic systems."

---

## Specific Actions to Take Now

### 1. Update README.md
Add dual branding to the main README:

```markdown
# Gobelo Grammar Toolkit (GGTK)
### The Zambian Languages NLP Engine

[![For Developers](https://img.shields.io/badge/For-Developers-blue)](https://github.com/gobelo/gobelo-grammar-toolkit)
[![Mobile App](https://img.shields.io/badge/Mobile_App-Gobelo_Languages-green)](https://gobelo.org/app)
[![Web Platform](https://img.shields.io/badge/Web_Platform-gobelo.org-orange)](https://gobelo.org)

A grammar-driven NLP library for the 7 official Zambian Bantu languages.

👥 **End Users:** Download "Gobelo Languages" mobile app  
👨‍💻 **Developers:** Install `pip install ggtk`  
🎓 **Educators:** Visit [gobelo.org](https://gobelo.org)  
🔬 **Researchers:** Explore our linguistic data
```

### 2. Add Branding Section to Documentation

Create `docs/BRANDING.md`:

```markdown
# GGTK Branding Guidelines

## Official Names

**Technical/Package Name:** GGTK (Gobelo Grammar Toolkit)
- Use in code, APIs, technical documentation
- Import path: `from ggtk import ...`
- Package: `pip install ggtk`

**User-Facing Products:**
- Mobile App: "Gobelo Languages"
- Web Platform: "Gobelo"
- Educational Tools: "Gobelo Classroom"

## Taglines

- Primary: "The Zambian Languages NLP Engine"
- Secondary: "Grammar-driven AI for 7 Zambian Bantu languages"
- Marketing: "Speak Zambian. Think Global."

## When to Use Which Name

| Context | Use | Example |
|---------|-----|---------|
| Code/Imports | `ggtk` | `from ggtk import ...` |
| Technical Docs | GGTK | "GGTK v1.0 released" |
| Mobile App | Gobelo Languages | "Download Gobelo Languages" |
| Marketing | Gobelo | "Join the Gobelo community" |
| Academic Papers | Gobelo Grammar Toolkit | "We used GGTK..." |
| General Public | Zambian Languages Toolkit | "Learn Zambian languages" |
```

### 3. Update pyproject.toml Description

```toml
[project]
name = "ggtk"
description = "Gobelo Grammar Toolkit - NLP engine for 7 Zambian Bantu languages"
```

### 4. Create Mobile App Mockup/Prototype

Even before building, create:
- App name: "Gobelo Languages"
- Logo design
- App store listing draft
- Feature list focused on end users (not developers)

---

## Comparison Table

| Aspect | Keep GGTK | Rename to ZLTK |
|--------|-----------|----------------|
| **Code Changes** | None | Massive (all imports, docs, tests) |
| **Breaking Changes** | Zero | Complete API break |
| **Migration Effort** | None | 40-80 hours minimum |
| **User Confusion** | None | High during transition |
| **SEO Impact** | Neutral | Negative (lost rankings) |
| **Brand Recognition** | Preserved | Lost, must rebuild |
| **Marketing Flexibility** | High (dual branding) | Limited (locked to new name) |
| **Mobile App Naming** | Flexible ("Gobelo Languages") | Constrained ("ZLTK" sounds technical) |
| **Academic Citations** | Stable | Fragmented |
| **Community Trust** | Maintained | Potentially damaged |
| **Time to Market** | Immediate | Delayed by migration |
| **Risk Level** | Low | Very High |

---

## Final Recommendation

### ✅ DO: Adopt Dual Branding Strategy

1. **Keep `ggtk`** as technical/package name (no code changes)
2. **Use "Gobelo Languages"** for mobile app and consumer products
3. **Update marketing materials** to emphasize "Zambian languages"
4. **Create audience-specific messaging** (developers vs. end users)
5. **Maintain technical excellence** while improving accessibility

### ❌ DON'T: Rename to ZLTK

1. Don't break existing code and integrations
2. Don't lose established brand recognition
3. Don't create unnecessary migration burden
4. Don't fragment the community
5. Don't sacrifice technical clarity for marketing

---

## Success Metrics

Track these to measure branding effectiveness:

### Technical Community (GGTK)
- GitHub stars/forks
- PyPI downloads
- Academic citations
- Developer adoption rate

### End Users (Gobelo Languages)
- Mobile app downloads
- Active users
- User satisfaction scores
- Language learning outcomes

### Overall Brand
- Website traffic
- Social media engagement
- Press mentions
- Partnership inquiries

---

## Conclusion

The hybrid dual-branding approach gives us the best of both worlds:

✅ **Technical Stability** - No breaking changes, preserved investment  
✅ **Market Appeal** - User-friendly names for mobile/web products  
✅ **Flexibility** - Different messaging for different audiences  
✅ **Future-Proof** - Can expand beyond Zambia without rebranding  
✅ **Low Risk** - No migration headaches or community confusion  

**"GGTK" remains the engine. "Gobelo Languages" becomes the experience.**

This is how successful platforms operate:
- TensorFlow (technical) → Various user-facing apps
- React (technical) → React Native, Next.js (products)
- PostgreSQL (technical) → Various database services

**GGTK is our foundation. Gobelo is our future.**

---

**Decision Date:** June 7, 2026  
**Status:** ✅ Recommendation Approved  
**Next Steps:** Implement Phase 1 (documentation updates)
