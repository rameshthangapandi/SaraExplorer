from app.agents.grounding import amounts, ungrounded
from app.agents.sara import _drop_lines_with, _grounding_base


def test_amount_formats():
    assert amounts("₹1 350, ₹12,600, ₹1,00,000 and ₹ 5000") == [1350, 12600, 100000, 5000]


def test_arithmetic_on_tool_numbers_is_grounded():
    assert ungrounded("5 × ₹1,350 = ₹6,750; total ₹4,950", {1350, 3600}) == []


def test_invented_amounts_are_caught_and_removed():
    reply = "Plan total ₹9,000\nTaxes and buffer ₹8,250\nEnjoy!"
    bad = ungrounded(reply, {9000})
    assert bad == [8250]
    assert "8,250" not in _drop_lines_with(reply, bad)


def test_base_includes_tools_and_user_only():
    msgs = [{"role": "user", "content": "budget 40000"}, {"role": "tool", "content": '{"total_inr": 23390}'},
            {"role": "assistant", "content": "I guess ₹99,999"}]
    assert _grounding_base(msgs) == {40000, 23390}
