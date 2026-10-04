"""Signal roles: a message read as 'what is this doing to me?', never as a verdict."""

import pytest

from ruko.language.templates import Renderer
from ruko.models.common import CONTENT_CODES, ReasonCode
from ruko.orchestrator.signal_view import role_keys, signal_roles

CONTENT_ROLES = {"pressure", "claims", "source"}


def test_every_reason_code_has_exactly_one_role():
    roles = signal_roles()
    assert set(roles) == {code.value for code in ReasonCode}


def test_content_codes_get_a_content_role_and_behavioural_codes_are_about_you():
    roles = signal_roles()
    for code in ReasonCode:
        expected = (
            roles[code.value] in CONTENT_ROLES
            if code in CONTENT_CODES
            else roles[code.value] == "you"
        )
        assert expected, code


def test_the_roles_do_not_judge_the_message_they_only_group_what_it_does():
    renderer = Renderer("en")
    for key in role_keys():
        text = renderer.text(key).lower()
        assert not any(word in text for word in ("scam", "fraud", "fake", "safe", "legit", "bad"))


@pytest.mark.parametrize("locale", ["en", "hi", "kn"])
def test_every_role_has_a_heading_in_every_language(locale):
    renderer = Renderer(locale)
    for key in role_keys():
        assert renderer.text(key)
    assert renderer.missing_keys == []
