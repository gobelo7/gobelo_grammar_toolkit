import pytest

from ggtk.core.config import GrammarConfig
from ggtk.core.loader import GobeloGrammarLoader
from ggtk.core.models import SyllabificationData
from ggtk.core.syllabifier import GrammarDrivenSyllabifier


@pytest.fixture(scope="module")
def bem_loader() -> GobeloGrammarLoader:
    return GobeloGrammarLoader(GrammarConfig(language="bem"))


def test_get_syllabification_returns_typed_config(bem_loader: GobeloGrammarLoader) -> None:
    syl = bem_loader.get_syllabification()

    assert isinstance(syl, SyllabificationData)
    assert syl.method == "rule_based_cv"
    assert syl.structure.max_onset_cluster_length == 3
    assert syl.structure.pattern == ("(C)V(N)", "CCV(N)", "CCCV(N)")
    assert "a" in syl.vowels
    assert "u" in syl.vowels


def test_syllabifier_applies_yaml_cluster_limits(bem_loader: GobeloGrammarLoader) -> None:
    syl = bem_loader.get_syllabification()
    result = GrammarDrivenSyllabifier().syllabify("mwana", syl, iso_code="bem")

    assert result.iso_code == "bem"
    assert result.texts == ("mwa", "na")
    assert result.count == 2


def test_syllabifier_handles_punctuation_and_case(bem_loader: GobeloGrammarLoader) -> None:
    syl = bem_loader.get_syllabification()
    result = GrammarDrivenSyllabifier().syllabify("Mwa-na!", syl, iso_code="bem")

    assert result.texts == ("Mwa", "na")
    assert result.word == "Mwa-na!"

