"""CFG break/continue/return and path probability / runtime weights."""

from __future__ import annotations

from md_generator.codeflow.graph.cfg_builder import build_cfg_from_ir
from md_generator.codeflow.graph.path_enumerator import enumerate_paths, find_cfg_end_id, find_cfg_start_id
from md_generator.codeflow.graph.path_probability import PathProbConfig, score_path
from md_generator.codeflow.graph.runtime_integration import apply_runtime_weights
from md_generator.codeflow.models.ir_cfg import IRMethod, IRStmt


def _paths(cfg):
    s, e = find_cfg_start_id(cfg), find_cfg_end_id(cfg)
    assert s and e
    return enumerate_paths(cfg, s, e, max_paths=50, max_depth=200).paths


def test_loop_break_exits_to_after_loop() -> None:
    ir = IRMethod(
        symbol_id="t.py::f",
        name="f",
        file_path="t.py",
        language="python",
        body=(
            IRStmt(
                kind="LOOP",
                condition="x",
                body=(
                    IRStmt(kind="CALL", target="g", label="call", line=2),
                    IRStmt(kind="BREAK", line=3),
                    IRStmt(kind="CALL", target="unreachable", label="call", line=4),
                ),
                line=1,
            ),
            IRStmt(kind="CALL", target="after", label="call", line=5),
        ),
    )
    cfg = build_cfg_from_ir(ir, max_nodes=200)
    paths = _paths(cfg)
    assert paths
    for p in paths:
        assert any(cfg.nodes[nid].kind == "LOOP_EXIT" for nid in p)
        assert "unreachable" not in "".join(cfg.nodes[nid].label for nid in p)


def test_return_skips_following_stmt_on_path() -> None:
    ir = IRMethod(
        symbol_id="t.py::f",
        name="f",
        file_path="t.py",
        language="python",
        body=(
            IRStmt(kind="CALL", target="a", label="call", line=1),
            IRStmt(kind="RETURN", label="return", line=2),
            IRStmt(kind="CALL", target="b", label="call", line=3),
        ),
    )
    cfg = build_cfg_from_ir(ir, max_nodes=200)
    paths = _paths(cfg)
    assert len(paths) == 1
    labs = [cfg.nodes[nid].label for nid in paths[0]]
    assert "a" in labs
    assert "b" not in labs


def test_if_then_else_path_scores() -> None:
    ir = IRMethod(
        symbol_id="t.py::f",
        name="f",
        file_path="t.py",
        language="python",
        body=(
            IRStmt(
                kind="IF",
                condition="c",
                body=(IRStmt(kind="CALL", target="t", label="call", line=2),),
                else_body=(IRStmt(kind="CALL", target="e", label="call", line=3),),
                line=1,
            ),
        ),
    )
    cfg = build_cfg_from_ir(ir, max_nodes=200)
    paths = _paths(cfg)
    assert len(paths) == 2
    pc = PathProbConfig(if_branch=0.5, loop_repeat=0.6)
    scores = [score_path(cfg, p, pc) for p in paths]
    assert abs(scores[0] - scores[1]) < 1e-9
    assert 0 < scores[0] < 1.0


def test_runtime_trace_sets_runtime_prob_and_affects_score() -> None:
    ir = IRMethod(
        symbol_id="t.py::f",
        name="f",
        file_path="t.py",
        language="python",
        body=(IRStmt(kind="CALL", target="a", label="call", line=1),),
    )
    cfg = build_cfg_from_ir(ir, max_nodes=50)
    s, e = find_cfg_start_id(cfg), find_cfg_end_id(cfg)
    assert s and e
    # single path START -> CALL -> END
    mid = None
    for n in cfg.nodes.values():
        if n.kind == "CALL":
            mid = n.id
            break
    assert mid
    trace = {"counts": {f"{s}->{mid}": 10, f"{mid}->{e}": 10}}
    apply_runtime_weights(cfg, trace)
    assert any(e.runtime_prob is not None for e in cfg.edges)
    pc = PathProbConfig()
    pth = [s, mid, e]
    assert score_path(cfg, pth, pc) == 1.0


def test_nested_loop_break_targets_inner_exit() -> None:
    inner = IRStmt(
        kind="LOOP",
        condition="inner",
        body=(IRStmt(kind="BREAK", line=3),),
        line=2,
    )
    outer = IRStmt(
        kind="LOOP",
        condition="outer",
        body=(inner,),
        line=1,
    )
    ir = IRMethod(
        symbol_id="t.py::f",
        name="f",
        file_path="t.py",
        language="python",
        body=(outer, IRStmt(kind="CALL", target="done", label="call", line=4)),
    )
    cfg = build_cfg_from_ir(ir, max_nodes=200)
    paths = _paths(cfg)
    assert paths
    loop_exits = sum(1 for n in cfg.nodes.values() if n.kind == "LOOP_EXIT")
    assert loop_exits == 2
