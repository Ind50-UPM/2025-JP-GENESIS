# Code for the calculator Agent

import ast
import operator

class CalculatorAgent:
    def __init__(self):
        self.ops = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
            ast.Pow: operator.pow,
            ast.USub: operator.neg
        }

    async def run(self, query: str):
        try:
            result = self._safe_eval(query)
            return {"Resultado": result}
        except Exception as e:
            return {"error": f"Error en el cálculo: {str(e)}"}

    def _safe_eval(self, expr):
        node = ast.parse(expr, mode="eval")

        def _eval(n):
            if isinstance(n, ast.Expression):
                return _eval(n.body)
            if isinstance(n, ast.Num):
                return n.value
            if isinstance(n, ast.BinOp):
                return self.ops[type(n.op)](_eval(n.left), _eval(n.right))
            if isinstance(n, ast.UnaryOp):
                return self.ops[type(n.op)](_eval(n.operand))
            raise ValueError("Expresión no válida")

        return _eval(node.body)
