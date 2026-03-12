name = "calc"
description = "Calculate a math expression"

import ast
import operator
import logging

def safe_calc(expression):
    try:
        operators = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
            ast.Pow: operator.pow,
            ast.Mod: operator.mod,
            ast.USub: operator.neg
        }
        
        def _eval(node):
            if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
                return node.value
            elif hasattr(ast, 'Num') and isinstance(node, getattr(ast, 'Num')):
                return node.n
            elif isinstance(node, ast.BinOp):
                return operators[type(node.op)](_eval(node.left), _eval(node.right))
            elif isinstance(node, ast.UnaryOp):
                return operators[type(node.op)](_eval(node.operand))
            else:
                raise TypeError(f"Unsupported node type: {type(node)}")

        expr = str(expression).replace("^", "**")
        node = ast.parse(expr, mode='eval').body
        return _eval(node)
    except Exception as e:
        logging.error(f"Math Error: {e}")
        return None

def run(math_expression):
    result = safe_calc(math_expression)
    if result is not None:
         return f"The result is {result}"
    else:
         return "I couldn't calculate that."
