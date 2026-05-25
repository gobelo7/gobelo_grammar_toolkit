Project description
Gobelo Grammar Toolkit (GGTK)
A grammar-driven NLP library for the 7 official Zambian Bantu languages, built on a single YAML grammar file as the authoritative linguistic source.

Languages: chiTonga · chiBemba · chiNyanja · siLozi · Luvale · Lunda · Kaonde
Status: v1.0.0 — chiTonga fully implemented; 6 languages registered, grammar data in progress
Python: 3.8+ License: MIT

View at:
https://test.pypi.org/project/gobelo-ggtk/1.0.0/
https://test.pypi.org/project/ggtk/1.0.0/

pip install -i https://test.pypi.org/simple/ gobelo-ggtk==1.0.0
or
pip install -i https://test.pypi.org/simple/ ggtk==1.0.0

Quick start
git clone https://github.com/gobelo/gobelo-grammar-toolkit
cd ggtk
pip install -e .              # installs ggtk CLI + library
from ggtk import GobeloGrammarLoader, GrammarConfig

loader   = GobeloGrammarLoader(GrammarConfig(language="chitonga"))
analyzer = MorphologicalAnalyzer(loader)

tok = analyzer.analyze("cilya")
print(tok.best.segmented)   # ci-ly-a
print(tok.best.gloss_line)  # NC7.SUBJ-ly-FV
Architecture
The grammar YAML is the single source of truth. No morpheme forms are hardcoded anywhere in the apps — every segmentation, generation, and concord lookup reads from the loader.