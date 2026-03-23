import yaml
from pathlib import Path
from typing import Dict, Any

class LanguageRegistry:
    """
    Automatically discovers and loads all YAML grammar files
    in the `languages/` directory.
    """
    _registry: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def load_all(cls, languages_dir: Path = None):
        if languages_dir is None:
            # Default: relative to this file
            languages_dir = Path(__file__).parent.parent / "languages"

        for yaml_file in languages_dir.glob("*.yaml"):
            language_name = yaml_file.stem  # filename without .yaml
            with open(yaml_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                cls._registry[language_name] = data

    @classmethod
    def get(cls, language_name: str) -> Dict[str, Any]:
        """
        Retrieve the grammar dictionary for a language.
        Raises KeyError if the language does not exist.
        """
        return cls._registry[language_name]

    @classmethod
    def list_languages(cls):
        """Return a list of all registered language names"""
        return list(cls._registry.keys())

###   How to use
### ==========================
from gobelo_grammar_toolkit.core.language_registry import LanguageRegistry

# Load all grammars at startup
LanguageRegistry.load_all()

# Access a language
chitonga_grammar = LanguageRegistry.get("chitonga")

# List all loaded languages
print(LanguageRegistry.list_languages())
# Output: ['chitonga', 'chibemba', 'chinyanja', 'luvale', 'kaonde', 'silozi', 'lunda']


Perfect — we can make Gobelo much more scalable by having a **dynamic language registry** that scans the `languages/` folder for YAML files and automatically loads them. That way, adding a new Bantu language is just a matter of dropping in a YAML file — **no code change required**.

Here’s a clean, Pythonic pattern:

---

## 1️⃣ Directory Structure

```
src/gobelo_grammar_toolkit/
├── languages/
│   ├── chitonga.yaml
│   ├── chibemba.yaml
│   ├── chinyanja.yaml
│   └── ...
├── core/
│   ├── __init__.py
│   └── language_registry.py
```

---

## 2️⃣ `language_registry.py`

```python
import yaml
from pathlib import Path
from typing import Dict, Any

class LanguageRegistry:
    """
    Automatically discovers and loads all YAML grammar files
    in the `languages/` directory.
    """
    _registry: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def load_all(cls, languages_dir: Path = None):
        if languages_dir is None:
            # Default: relative to this file
            languages_dir = Path(__file__).parent.parent / "languages"

        for yaml_file in languages_dir.glob("*.yaml"):
            language_name = yaml_file.stem  # filename without .yaml
            with open(yaml_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                cls._registry[language_name] = data

    @classmethod
    def get(cls, language_name: str) -> Dict[str, Any]:
        """
        Retrieve the grammar dictionary for a language.
        Raises KeyError if the language does not exist.
        """
        return cls._registry[language_name]

    @classmethod
    def list_languages(cls):
        """Return a list of all registered language names"""
        return list(cls._registry.keys())
```

---

## 3️⃣ How to Use

```python
from gobelo_grammar_toolkit.core.language_registry import LanguageRegistry

# Load all grammars at startup
LanguageRegistry.load_all()

# Access a language
chitonga_grammar = LanguageRegistry.get("chitonga")

# List all loaded languages
print(LanguageRegistry.list_languages())
# Output: ['chitonga', 'chibemba', 'chinyanja', 'luvale', 'kaonde', 'silozi', 'lunda']
```

---

## 4️⃣ Benefits

1. ✅ **Drop-in scalability**: just drop `new_language.yaml` in `languages/`.
2. ✅ **Centralized registry**: every module can use `LanguageRegistry.get(name)` to access grammar.
3. ✅ **No hardcoded imports**: eliminates `from chitonga import ...` patterns.
4. ✅ **Testable**: tests can iterate over `LanguageRegistry.list_languages()` to validate every YAML automatically.

---

## 5️⃣ Optional: Auto-load on import

If you want the registry loaded immediately when the package is imported:

```python
# in core/__init__.py
from .language_registry import LanguageRegistry

LanguageRegistry.load_all()
```

Then any module can just call:

```python
from gobelo_grammar_toolkit.core.language_registry import LanguageRegistry

grammar = LanguageRegistry.get("chibemba")
```

---

This **one-class change** eliminates the need for 100s of hardcoded references in your toolkit and is **perfect for growing your Bantu language coverage**.

If you want, I can also **draft a pytest-friendly auto-test** that goes through **every YAML** and ensures it conforms to a schema — so you catch errors before they hit runtime.

Do you want me to do that next?
