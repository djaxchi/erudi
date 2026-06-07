"""PR3 — calculator tool (issue #81, problem #4).

LLMs predict tokens, they don't compute: Gemma-3-4b-4bit added 4×4-digit
numbers wrong on every eval run (different wrong totals each time) while
displaying the correct operands. The fix is a deterministic calculator
TOOL wired into the agent loop. The evaluator is a strict AST whitelist —
never ``eval``: no names, no calls, no attributes, numbers and arithmetic
operators only.
"""

import pytest

from src.agents.tools import calculator, evaluate_arithmetic

pytestmark = pytest.mark.unit


class TestEvaluateArithmetic:
    def test_multi_operand_addition(self):
        # The exact T5 failure case: every eval run got this wrong.
        assert evaluate_arithmetic("1240 + 1378 + 1456 + 1689") == "5763"

    def test_operator_coverage(self):
        assert evaluate_arithmetic("(290 - 89) * 12") == "2412"
        assert evaluate_arithmetic("2 ** 10") == "1024"
        assert evaluate_arithmetic("17 // 5") == "3"
        assert evaluate_arithmetic("17 % 5") == "2"
        assert evaluate_arithmetic("-5 + 3") == "-2"

    def test_float_results_are_trimmed(self):
        assert evaluate_arithmetic("5763 / 4") == "1440.75"
        assert evaluate_arithmetic("10 / 2") == "5"  # no trailing .0

    def test_division_by_zero_is_a_clean_error(self):
        with pytest.raises(ValueError, match="division by zero"):
            evaluate_arithmetic("1 / 0")

    @pytest.mark.parametrize(
        "hostile",
        [
            "__import__('os').system('rm -rf /')",
            "open('/etc/passwd')",
            "a + 1",                      # names rejected
            "(1).__class__",              # attributes rejected
            "[1, 2][0]",                  # subscripts rejected
            "1 if True else 2",           # conditionals rejected
            "lambda: 1",
            "1; 2",
            "",
            "   ",
        ],
    )
    def test_non_arithmetic_input_is_rejected(self, hostile):
        with pytest.raises(ValueError):
            evaluate_arithmetic(hostile)

    def test_huge_exponent_is_rejected(self):
        # 9**9**9 would hang/explode memory — the evaluator must bound it.
        with pytest.raises(ValueError):
            evaluate_arithmetic("9 ** 9 ** 9")


class TestCalculatorTool:
    def test_is_a_langchain_tool_with_schema(self):
        assert calculator.name == "calculator"
        assert "expression" in calculator.args

    def test_invoke_computes(self):
        assert calculator.invoke({"expression": "1240+1378+1456+1689"}) == "5763"

    def test_invoke_reports_errors_as_text(self):
        # Tool errors must come back as a message the model can react to,
        # not crash the agent loop.
        result = calculator.invoke({"expression": "total + 12"})
        assert "Error" in result
