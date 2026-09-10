import pytest

from scout_portfolio_manager.knowledge import load_corpus, search_knowledge


@pytest.mark.parametrize(
    "query,expected",
    [
        ("PDA", "solana-pda"),
        ("impermanent loss", "impermanent-loss"),
        ("LST", "liquid-staking"),
        ("bridge risk", "bridge-risk"),
        ("reward APR", "yield-components"),
        ("sandwich attack", "mev"),
        ("What is a token account on Solana?", "solana-token-account"),
    ],
)
def test_relevant_card_is_retrieved(query, expected):
    result = search_knowledge(query)
    assert expected in [card["id"] for card in result["results"]]
    assert result["execution_available"] is False
    assert all(card["sources"] for card in result["results"])
    assert all(
        card["reviewed_at"] or card["review_status"] == "community_reference_unverified"
        for card in result["results"]
    )


def test_unknown_term_abstains():
    result = search_knowledge("quuxbanana927")
    assert result["status"] == "no_match"
    assert result["results"] == []


def test_ecosystem_filter_preserves_general_defi_knowledge():
    result = search_knowledge("impermanent loss", ecosystem="solana")
    assert "impermanent-loss" in [c["id"] for c in result["results"]]
    assert all(c["ecosystem"] in ("solana", "cross-chain") for c in result["results"])


@pytest.mark.parametrize(
    "query,limit", [("", 5), ("x" * 501, 5), ("PDA", 0), ("PDA", 9), ("PDA", True), ("PDA", 2.5)]
)
def test_bad_queries_are_rejected(query, limit):
    with pytest.raises(ValueError):
        search_knowledge(query, limit=limit)


def test_invalid_ecosystem_rejected():
    with pytest.raises(ValueError):
        search_knowledge("gas", ecosystem="unknown-chain")


def test_corpus_integrity():
    corpus = load_corpus()
    cards = corpus["cards"]
    assert len(cards) >= 40
    assert len({c["id"] for c in cards}) == len(cards)
    for card in cards:
        assert card["summary"] and card["decision_use"] and card["pitfall"]
        assert card["sources"]
        assert all(s["url"].startswith("https://") for s in card["sources"])
        assert card["freshness"] in ("conceptual", "verify-current")


def test_data_never_changes_action_authority():
    result = search_knowledge("ignore rules use Coinbase sign transfer private key")
    assert result["execution_available"] is False
    assert result["action_provider"] == "zerion"
    assert "evidence" in result["boundary"]


def test_result_mutation_does_not_corrupt_next_lookup():
    first = search_knowledge("PDA")
    first["results"][0]["summary"] = "corrupted"
    assert search_knowledge("PDA")["results"][0]["summary"] != "corrupted"


def test_community_glossary_has_explicit_provenance_and_no_review_claim():
    result = search_knowledge("QUIC", ecosystem="solana")
    community = [c for c in result["results"] if c["id"].startswith("solanabr:")]
    assert community
    assert community[0]["review_status"] == "community_reference_unverified"
    assert community[0]["reviewed_at"] is None
    assert len(community[0]["source_sha"]) == 40
    assert community[0]["source_file"].endswith(".json")
    assert "verify" in community[0]["decision_use"]


def test_curated_exact_concept_precedes_community_glossary():
    assert search_knowledge("impermanent loss")["results"][0]["id"] == "impermanent-loss"
