# Naming Decision Summary: GGTK vs ZLTK

**Date:** June 7, 2026  
**Decision:** ✅ Maintain `ggtk` with dual branding strategy  
**Status:** Approved and Implemented

---

## The Question

> "Should we rename GGTK (Gobelo Grammar Toolkit) to ZLTK (Zambia Languages Toolkit), especially considering the mobile app?"

---

## The Answer: NO - Keep GGTK, Adopt Dual Branding ⭐

### Why Not Rename?

Renaming from `ggtk` to `zltk` would cause:

❌ **Breaking Changes Everywhere:**
```python
# All existing code breaks
from ggtk import GobeloGrammarLoader  # ❌ ImportError
from zltk import GobeloGrammarLoader  # ✅ But nobody's code uses this yet
```

❌ **Massive Migration Cost:**
- Update all imports in codebase
- Rewrite all documentation
- Update all tutorials and examples
- Change PyPI package name (lose existing installs)
- Rename GitHub repository
- Break all external integrations
- Confuse existing users

❌ **Lost Brand Equity:**
- Any recognition of "GGTK" disappears
- Academic citations become fragmented
- SEO rankings drop
- Community trust damaged

❌ **Technical Debt:**
- Must maintain backward compatibility OR force migration
- Support two versions during transition
- Risk of community fragmentation

**Estimated Cost of Renaming:** 40-80 hours + significant user confusion

---

## The Better Solution: Dual Branding ✅

### Technical Layer (Unchanged)
```
Package Name:     ggtk
Import Path:      from ggtk import ...
CLI Command:      ggtk analyze --lang toi "balya"
PyPI Package:     ggtk
GitHub Repo:      gobelo/gobelo-grammar-toolkit
Code Directory:   ggtk/
```

**No changes needed. Zero breaking changes.**

### User-Facing Layer (Rebranded)

#### Mobile App
**Name:** "Gobelo Languages"  
**Tagline:** "Learn Zambian Languages with AI"  
**Positioning:** Consumer-friendly, accessible, engaging

#### Web Platform
**Name:** "Gobelo"  
**URL:** gobelo.org  
**Tagline:** "Your Gateway to Zambian Languages"

#### Documentation
**Title:** "Gobelo Grammar Toolkit (GGTK)"  
**Subtitle:** "The Zambian Languages NLP Engine"  
**Audience:** Developers, researchers, linguists

#### Marketing
**Headline:** "Speak Zambian. Think Global."  
**Subhead:** "Powered by GGTK - Advanced AI for 7 Zambian languages"

---

## What We've Done

### 1. Created Strategic Documents

✅ [`docs/BRANDING_STRATEGY.md`](file:///c:/gobelo/apps/ggtk/docs/BRANDING_STRATEGY.md)
- Comprehensive branding guidelines
- When to use which name
- Audience-specific messaging
- Implementation roadmap

✅ [`docs/MOBILE_APP_CONCEPT.md`](file:///c:/gobelo/apps/ggtk/docs/MOBILE_APP_CONCEPT.md)
- Complete mobile app vision
- Feature specifications
- Business model
- Go-to-market strategy
- Technical architecture

✅ Updated [`README.md`](file:///c:/gobelo/apps/ggtk/README.md)
- Added audience-specific sections
- Clear positioning for different users
- Links to mobile app (future)

### 2. Maintained Technical Stability

✅ No code changes required  
✅ All imports remain `from ggtk import ...`  
✅ Package name stays `ggtk` on PyPI  
✅ CLI command remains `ggtk`  
✅ Existing documentation still valid  

### 3. Enabled Marketing Flexibility

✅ Can position differently for different audiences  
✅ Mobile app can have consumer-friendly name  
✅ Technical users get precise, accurate naming  
✅ No confusion between products  

---

## Comparison: Before vs After

### Before (Single Brand - GGTK Only)

```
Everything: "Gobelo Grammar Toolkit (GGTK)"

Pros:
✓ Consistent naming
✓ Technically accurate

Cons:
✗ Sounds academic/technical
✗ May intimidate non-technical users
✗ Doesn't emphasize "Zambian languages"
✗ Less appealing for mobile app store
```

### After (Dual Branding)

```
Technical: "GGTK (Gobelo Grammar Toolkit)"
Mobile App: "Gobelo Languages"
Web Platform: "Gobelo"
Marketing: "Zambian Languages NLP Engine"

Pros:
✓ Technically precise for developers
✓ User-friendly for consumers
✓ Emphasizes Zambian language focus
✓ Flexible positioning per audience
✓ No breaking changes
✓ Best of both worlds

Cons:
⚠ Slightly more complex messaging
(Mitigated by clear documentation)
```

---

## Real-World Examples of Dual Branding

This strategy is proven and widely used:

| Technical Name | User-Facing Products | Company |
|----------------|---------------------|---------|
| TensorFlow | TensorFlow Lite, TF.js, TFX | Google |
| React | React Native, Next.js, Gatsby | Meta |
| PostgreSQL | Heroku Postgres, AWS RDS, Supabase | Multiple |
| Kubernetes | GKE, EKS, AKS, OpenShift | Multiple |
| Linux | Ubuntu, Fedora, Red Hat | Multiple |
| LLVM | Swift, Rust compiler, Clang | Multiple |

**Pattern:** Strong technical foundation + diverse user-facing products

**GGTK follows this pattern:**
- GGTK = Technical foundation (like TensorFlow)
- Gobelo Languages = Mobile app (like TensorFlow Lite)
- Gobelo.org = Web platform (like TF.js)

---

## Implementation Checklist

### Completed ✅

- [x] Analyzed naming options
- [x] Created branding strategy document
- [x] Developed mobile app concept
- [x] Updated README.md with dual branding
- [x] Documented decision rationale
- [x] Verified no code changes needed

### Next Steps 📋

#### Phase 1: Documentation (Week 1)
- [ ] Create `docs/BRANDING.md` (quick reference)
- [ ] Update all docstrings to mention "Zambian languages"
- [ ] Add taglines to key documentation pages
- [ ] Create marketing one-pager

#### Phase 2: Web Presence (Month 1)
- [ ] Register gobelo.org domain
- [ ] Build landing page
- [ ] Create social media accounts (@GobeloLanguages)
- [ ] Write blog post announcing rebrand

#### Phase 3: Mobile App (Months 2-6)
- [ ] Design app icon/logo ("Gobelo Languages")
- [ ] Create app store listings
- [ ] Develop MVP (see MOBILE_APP_CONCEPT.md)
- [ ] Beta test with Zambian users

#### Phase 4: Community (Ongoing)
- [ ] Announce to developer community
- [ ] Present at linguistics conferences
- [ ] Partner with Zambian schools
- [ ] Build educator network

---

## Messaging Guide

### For Developers/Researchers

```
"The Gobelo Grammar Toolkit (GGTK) is a grammar-driven NLP 
library for 7 Zambian Bantu languages. Install via pip:

    pip install ggtk

Import in Python:

    from ggtk import GobeloGrammarLoader, GrammarConfig

Documentation: https://github.com/gobelo/gobelo-grammar-toolkit
```

### For End Users (Mobile App)

```
"Download Gobelo Languages - the easiest way to learn 
Zambian languages!

✨ AI-powered lessons for chiTonga, chiBemba, Nyanja & more
🎯 Personalized learning paths
🗣️ Practice pronunciation with speech recognition
🌍 Discover Zambian culture through language

Available on iOS and Android. Start your journey today!"
```

### For Educators

```
"Gobelo Classroom brings Zambian languages into the digital age.

Create interactive lessons, track student progress, and access 
comprehensive linguistic resources for all 7 official Zambian 
languages.

Built on GGTK - the most advanced computational grammar of 
Zambian Bantu languages.

Request a demo: education@gobelo.org"
```

### For Press/Media

```
"Gobelo, a Zambian language technology startup, today announced 
the launch of 'Gobelo Languages' - a mobile app that uses 
artificial intelligence to make learning Zambian languages 
accessible and engaging.

The app is powered by GGTK (Gobelo Grammar Toolkit), an 
open-source NLP engine that represents the most comprehensive 
computational description of Zambian Bantu languages ever created.

'Speak Zambian. Think Global.' - Gobelo makes it possible."
```

---

## FAQ

### Q: Won't having two names confuse people?

**A:** No, because they serve different purposes:
- **GGTK** = The engine (developers/researchers)
- **Gobelo Languages** = The product (end users)

Just like:
- TensorFlow (engine) vs. various apps built with it
- Linux (kernel) vs. Ubuntu/Fedora (distributions)

Clear documentation explains the relationship.

### Q: What if someone searches for "Zambia Languages Toolkit"?

**A:** They'll find us through:
- SEO optimization for those keywords
- Marketing materials using "Zambian languages" terminology
- App store descriptions
- Website content

The technical name doesn't limit discoverability.

### Q: Should we add "Zambian" to the package name?

**A:** No, because:
- Package names should be short and memorable
- `ggtk` is already established
- Description field can say "Zambian languages"
- Keywords/tags handle searchability

Example from PyPI:
```
Name: ggtk
Description: Gobelo Grammar Toolkit - NLP engine for 7 Zambian Bantu languages
Keywords: zambian, bantu, nlp, morphology, languages
```

### Q: What about international expansion beyond Zambia?

**A:** Dual branding actually helps:
- **GGTK** can expand to other Bantu languages (technically neutral)
- **Gobelo Languages** can add "East African Languages" section
- Brand isn't locked to "Zambia" specifically
- Can create regional variants: "Gobelo East Africa", etc.

### Q: Will academics take "Gobelo Languages" seriously?

**A:** Academics will use **GGTK**, not the mobile app name:
- Research papers cite "Gobelo Grammar Toolkit (GGTK)"
- Conference presentations reference GGTK
- Academic collaborations use technical name
- Mobile app name is irrelevant to research credibility

### Q: Is "Gobelo" a real word?

**A:** Yes/No (depends on context):
- It's the project/brand name
- Represents the organization behind GGTK
- Can be positioned as meaning "together" or "community" in local context
- Brand names don't need to be dictionary words (Google, Amazon, Apple)

---

## Success Metrics

Track these to validate the dual branding strategy:

### Technical Community (GGTK)
- [ ] GitHub stars: Target 500+ in Year 1
- [ ] PyPI downloads: Target 10,000+ in Year 1
- [ ] Academic citations: Track via Google Scholar
- [ ] Developer satisfaction: Survey NPS score

### End Users (Gobelo Languages)
- [ ] App downloads: Target 50,000+ in Year 1
- [ ] Active users: 30% MAU target
- [ ] App store rating: 4.5+ stars
- [ ] User retention: 40% Day-30 retention

### Brand Recognition
- [ ] Search volume for "Gobelo" vs "GGTK"
- [ ] Social media followers
- [ ] Press mentions
- [ ] Partnership inquiries

If both metrics grow, dual branding is working! ✅

---

## Conclusion

### The Decision: ✅ Keep GGTK, Add Gobelo Branding

**Rationale:**
1. Zero breaking changes
2. Maximum flexibility
3. Proven strategy (used by major tech companies)
4. Serves all audiences effectively
5. Future-proof for expansion

**Implementation:**
- Technical layer: Unchanged (`ggtk`)
- User layer: Rebranded ("Gobelo Languages")
- Documentation: Updated with dual positioning
- Mobile app: Consumer-friendly name

**Result:**
Best of both worlds - technical precision + mass appeal.

---

### Final Thought

> "GGTK is the engine. Gobelo is the experience. Together, they make Zambian languages accessible to the world."

This isn't just a naming decision - it's a strategic positioning that enables:
- ✅ Academic credibility (GGTK)
- ✅ Mass market appeal (Gobelo Languages)
- ✅ Developer adoption (clear API)
- ✅ User engagement (friendly UX)
- ✅ Cultural preservation (mission-driven)
- ✅ Business sustainability (revenue potential)

**We're not choosing between GGTK and ZLTK. We're building both - GGTK as the foundation, Gobelo as the future.**

---

**Decision Date:** June 7, 2026  
**Implemented By:** AI Assistant + User Collaboration  
**Status:** ✅ Complete  
**Next:** Execute Phase 1 (documentation updates)

---

## Related Documents

- [`docs/BRANDING_STRATEGY.md`](file:///c:/gobelo/apps/ggtk/docs/BRANDING_STRATEGY.md) - Detailed branding guidelines
- [`docs/MOBILE_APP_CONCEPT.md`](file:///c:/gobelo/apps/ggtk/docs/MOBILE_APP_CONCEPT.md) - Mobile app vision and plan
- [`ENHANCEMENT_AUDIT_SUMMARY.md`](file:///c:/gobelo/apps/ggtk/ENHANCEMENT_AUDIT_SUMMARY.md) - Technical enhancements
- [`README.md`](file:///c:/gobelo/apps/ggtk/README.md) - Updated with dual branding
