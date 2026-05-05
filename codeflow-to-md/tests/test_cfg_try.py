"""CFG try/catch/finally shape and path enumeration."""

from __future__ import annotations

from md_generator.codeflow.graph.cfg_builder import build_cfg_from_ir
from md_generator.codeflow.graph.path_enumerator import enumerate_paths, find_cfg_end_id, find_cfg_start_id
from md_generator.codeflow.generators.cfg_paths_markdown import paths_to_markdown
from md_generator.codeflow.models.ir_cfg import IRMethod, IRStmt


def _paths(cfg):
    s, e = find_cfg_start_id(cfg), find_cfg_end_id(cfg)
    assert s and e
    return enumerate_paths(cfg, s, e, max_paths=50, max_depth=200).paths


def _kinds(cfg, path: list[str]) -> list[str]:
    return [cfg.nodes[nid].kind for nid in path]


def test_try_catch_two_paths_no_finally() -> None:
    ir = IRMethod(
        symbol_id="f.java::M.m",
        name="m",
        file_path="f.java",
        language="java",
        body=(
            IRStmt(
                kind="TRY",
                body=(IRStmt(kind="CALL", target="A", label="call", line=1),),
                cases=(
                    (
                        "except:Exception",
                        (IRStmt(kind="CALL", target="B", label="call", line=2),),
                    ),
                ),
                else_body=(),
                line=1,
            ),
            IRStmt(kind="CALL", target="C", label="call", line=3),
        ),
    )
    cfg = build_cfg_from_ir(ir, max_nodes=500)
    paths = _paths(cfg)
    assert len(paths) == 2
    kinds0 = set(_kinds(cfg, paths[0]))
    kinds1 = set(_kinds(cfg, paths[1]))
    assert "FINALLY" not in kinds0 and "FINALLY" not in kinds1
    assert all("MERGE" in _kinds(cfg, p) for p in paths)
    assert any("CATCH" in _kinds(cfg, p) for p in paths)
    exc = [e for e in cfg.edges if (e.label or "").startswith("exception:")]
    assert len(exc) == 1
    assert exc[0].label == "exception:Exception"


def test_try_catch_finally_finally_on_all_paths() -> None:
    ir = IRMethod(
        symbol_id="f.java::M.m",
        name="m",
        file_path="f.java",
        language="java",
        body=(
            IRStmt(
                kind="TRY",
                body=(IRStmt(kind="CALL", target="A", label="call", line=1),),
                cases=(
                    (
                        "except:Exception",
                        (IRStmt(kind="CALL", target="B", label="call", line=2),),
                    ),
                ),
                else_body=(IRStmt(kind="CALL", target="D", label="call", line=4),),
                line=1,
            ),
            IRStmt(kind="CALL", target="C", label="call", line=5),
        ),
    )
    cfg = build_cfg_from_ir(ir, max_nodes=500)
    paths = _paths(cfg)
    assert len(paths) == 2
    for p in paths:
        ks = _kinds(cfg, p)
        assert "FINALLY" in ks
        assert ks.index("FINALLY") < ks.index("END")
    no_exc = [e for e in cfg.edges if e.label == "no_exception"]
    assert no_exc and all(cfg.nodes[e.target].kind == "FINALLY" for e in no_exc)


def test_multiple_catch_parallel_paths() -> None:
    ir = IRMethod(
        symbol_id="f.java::M.m",
        name="m",
        file_path="f.java",
        language="java",
        body=(
            IRStmt(
                kind="TRY",
                body=(IRStmt(kind="CALL", target="A", label="call", line=1),),
                cases=(
                    (
                        "except:IOException",
                        (IRStmt(kind="CALL", target="B", label="call", line=2),),
                    ),
                    (
                        "except:Exception",
                        (IRStmt(kind="CALL", target="C", label="call", line=3),),
                    ),
                ),
                else_body=(),
                line=1,
            ),
        ),
    )
    cfg = build_cfg_from_ir(ir, max_nodes=500)
    paths = _paths(cfg)
    assert len(paths) == 3
    catch_labs = {cfg.nodes[nid].label for p in paths for nid in p if cfg.nodes[nid].kind == "CATCH"}
    assert "except:IOException" in catch_labs and "except:Exception" in catch_labs
    exc_labels = {e.label for e in cfg.edges if (e.label or "").startswith("exception:")}
    assert exc_labels == {"exception:IOException", "exception:Exception"}


def test_paths_markdown_includes_exception_flow() -> None:
    ir = IRMethod(
        symbol_id="f.java::M.m",
        name="m",
        file_path="f.java",
        language="java",
        body=(
            IRStmt(
                kind="TRY",
                body=(IRStmt(kind="CALL", target="A", label="call", line=1),),
                cases=(("except:E", (IRStmt(kind="CALL", target="B", label="call", line=2),)),),
                else_body=(),
                line=1,
            ),
        ),
    )
    cfg = build_cfg_from_ir(ir, max_nodes=500)
    paths = _paths(cfg)
    md = paths_to_markdown(cfg, paths, cfg.nodes)
    assert "## Exception flow" in md
    assert "exception:" in md
