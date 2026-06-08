"""Agent tools — deterministic calculator (issue #81, problem #4).

LLMs predict tokens, they don't compute: small quantized models add
multi-digit numbers wrong with full confidence (measured: a different
wrong total on every eval run, correct operands displayed alongside).
The agent therefore carries a deterministic ``calculator`` tool; models
with native function calling (Qwen, Mistral, Llama 3.1+…) invoke it
through the standard agent loop. Models without it (e.g. Gemma 3 — no
tool format in its chat template, never emits ``tool_calls``) fall back
to the KB prompt's no-mental-math rule.

The evaluator is a strict AST whitelist — NEVER ``eval``: numbers and
arithmetic operators only (no names, calls, attributes, subscripts).
"""

from __future__ import annotations

import ast
import operator

from langchain_core.tools import tool

_BINARY_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY_OPERATORS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}

# Bounds against degenerate inputs (9**9**9 would hang/explode memory).
_MAX_EXPRESSION_LENGTH = 200
_MAX_POWER_EXPONENT = 1000
_MAX_ABS_VALUE = 1e15


def _evaluate_node(node: ast.AST) -> float:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return node.value
        raise ValueError(f"unsupported constant: {node.value!r}")
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPERATORS:
        return _UNARY_OPERATORS[type(node.op)](_evaluate_node(node.operand))
    if isinstance(node, ast.BinOp) and type(node.op) in _BINARY_OPERATORS:
        left = _evaluate_node(node.left)
        right = _evaluate_node(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > _MAX_POWER_EXPONENT:
            raise ValueError("exponent too large")
        try:
            result = _BINARY_OPERATORS[type(node.op)](left, right)
        except ZeroDivisionError:
            raise ValueError("division by zero")
        if abs(result) > _MAX_ABS_VALUE:
            raise ValueError("result too large")
        return result
    raise ValueError(f"unsupported syntax: {type(node).__name__}")


def evaluate_arithmetic(expression: str) -> str:
    """Evaluate a pure arithmetic expression deterministically.

    Returns the result as a string (integers without a trailing ``.0``).

    Raises:
        ValueError: empty input, non-arithmetic syntax, division by zero,
            or out-of-bounds magnitude.
    """
    expression = (expression or "").strip()
    if not expression:
        raise ValueError("empty expression")
    if len(expression) > _MAX_EXPRESSION_LENGTH:
        raise ValueError("expression too long")
    try:
        parsed = ast.parse(expression, mode="eval")
    except SyntaxError:
        raise ValueError("invalid arithmetic expression")
    result = _evaluate_node(parsed.body)
    if isinstance(result, float) and result.is_integer():
        return str(int(result))
    return str(result)


@tool
def calculator(expression: str) -> str:
    """Compute an arithmetic expression exactly. Use this for EVERY
    calculation instead of doing mental math: additions, subtractions,
    multiplications, divisions, percentages, powers.

    Args:
        expression: A pure arithmetic expression, e.g. "1240 + 1378 + 1456"
            or "(290 - 89) * 12". Numbers and + - * / // % ** ( ) only.
    """
    try:
        return evaluate_arithmetic(expression)
    except ValueError as exc:
        # Text the model can react to — never crash the agent loop.
        return f"Error: {exc}. Provide a pure arithmetic expression."
