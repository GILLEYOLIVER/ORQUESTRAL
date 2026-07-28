from app.modules.support.engagement_service import protected_digest, satisfaction_summary


def test_protected_digest_never_returns_comment() -> None:
    comment = "Cliente informou um dado sensível"
    digest = protected_digest(comment)
    assert digest and digest != comment and len(digest) == 64


def test_satisfaction_summary_is_deterministic() -> None:
    summary = satisfaction_summary([(5, 4, 3), (1, 2, 5), (4, 5, 4)])
    assert summary.responses == 3
    assert summary.overall_average == 3.33
    assert summary.resolution_average == 3.67
    assert summary.effort_average == 4
    assert summary.promoters == 2
    assert summary.detractors == 1


def test_empty_satisfaction_summary_is_explicit() -> None:
    summary = satisfaction_summary([])
    assert summary.responses == 0
    assert summary.overall_average == 0

