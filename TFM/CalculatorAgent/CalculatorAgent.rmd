Code for the calculator Agent


# calc_stats.py
import numpy as np

def calc_stats(operation: str, values):
    arr = np.array(values, dtype=float)

    if operation == "mean":
        return {"mean": float(arr.mean())}

    if operation == "sum":
        return {"sum": float(arr.sum())}

    if operation == "max":
        return {"max": float(arr.max())}

    if operation == "min":
        return {"min": float(arr.min())}

    if operation == "std":
        return {"std": float(arr.std())}

    return {"error": "Operación desconocida"}
