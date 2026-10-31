"""Inventory every Python function in a pinned DeepInfer tree and pick the ones whose shape
could fall in an existing integer import profile (single `return <expr>` over parameters and
integer literals, arithmetic/comparison/conditional only). Writes candidates as standalone
sources for the real adapters; it decides nothing about acceptance itself."""
import ast, json, sys
from pathlib import Path

root = Path(sys.argv[1]); out = Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
ARITH = (ast.Add, ast.Sub, ast.Mult, ast.FloorDiv, ast.Mod, ast.LShift, ast.RShift,
         ast.BitAnd, ast.BitOr, ast.BitXor, ast.Div, ast.Pow)

def pure_int_expr(node, params):
    if isinstance(node, ast.Name): return node.id in params
    if isinstance(node, ast.Constant): return isinstance(node.value, int) and not isinstance(node.value, bool)
    if isinstance(node, ast.BinOp): return isinstance(node.op, ARITH) and pure_int_expr(node.left, params) and pure_int_expr(node.right, params)
    if isinstance(node, ast.UnaryOp): return isinstance(node.op, (ast.USub, ast.Invert, ast.UAdd)) and pure_int_expr(node.operand, params)
    if isinstance(node, ast.Compare): return all(pure_int_expr(n, params) for n in [node.left, *node.comparators])
    if isinstance(node, ast.IfExp): return all(pure_int_expr(n, params) for n in (node.test, node.body, node.orelse))
    return False

rows = []; total = 0; files = 0
for f in sorted(root.rglob('*.py')):
    rel = f.relative_to(root).as_posix(); files += 1
    src = f.read_text(encoding='utf-8')
    tree = ast.parse(src)
    lines = src.splitlines()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)): continue
        total += 1
        a = node.args
        params = [p.arg for p in a.posonlyargs + a.args + a.kwonlyargs]
        body = [s for s in node.body if not (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant) and isinstance(s.value.value, str))]
        if not (len(body) == 1 and isinstance(body[0], ast.Return) and body[0].value is not None): continue
        if a.vararg or a.kwarg or node.decorator_list or not params: continue
        if not pure_int_expr(body[0].value, set(params)): continue
        seg = '\n'.join(lines[node.lineno - 1: node.end_lineno])
        name = f'{len(rows):03d}_{node.name}'
        (out / f'{name}.py').write_text(ast.unparse(node) + '\n')
        rows.append({'id': name, 'file': rel, 'line': node.lineno, 'name': node.name,
                     'params': params, 'annotated': any(p.annotation for p in a.args), 'source': seg})
json.dump({'files': files, 'functions': total, 'candidates': rows}, open(out / 'candidates.json', 'w'), indent=1)
print(f'files={files} functions={total} candidates={len(rows)}')
for r in rows: print(f"{r['id']}  {r['file']}:{r['line']}  {r['source'].splitlines()[-1].strip()[:90]}")
