<?php
declare(strict_types=1);

// Usage: php dump.php <file.php> [fileKey]

if ($argc < 2) {
    fwrite(STDERR, "usage: php dump.php <file.php> [fileKey]\n");
    exit(2);
}

$autoload = __DIR__ . '/vendor/autoload.php';
if (!is_file($autoload)) {
    echo json_encode(['error' => 'run composer install in tools/codeflow_php_dump'], JSON_UNESCAPED_SLASHES) . "\n";
    exit(1);
}

require $autoload;

use PhpParser\Error;
use PhpParser\Node;
use PhpParser\Node\Expr\FuncCall;
use PhpParser\Node\Expr\MethodCall;
use PhpParser\Node\Expr\StaticCall;
use PhpParser\Node\Stmt\Break_;
use PhpParser\Node\Stmt\Case_;
use PhpParser\Node\Stmt\Catch_;
use PhpParser\Node\Stmt\Class_;
use PhpParser\Node\Stmt\ClassMethod;
use PhpParser\Node\Stmt\Continue_;
use PhpParser\Node\Stmt\Do_;
use PhpParser\Node\Stmt\Expression;
use PhpParser\Node\Stmt\For_;
use PhpParser\Node\Stmt\Foreach_;
use PhpParser\Node\Stmt\Function_;
use PhpParser\Node\Stmt\If_;
use PhpParser\Node\Stmt\Return_;
use PhpParser\Node\Stmt\Switch_;
use PhpParser\Node\Stmt\Throw_;
use PhpParser\Node\Stmt\Try_;
use PhpParser\Node\Stmt\While_;
use PhpParser\NodeTraverser;
use PhpParser\NodeVisitorAbstract;
use PhpParser\ParserFactory;
use PhpParser\PrettyPrinter\Standard;

/** CFG-oriented IR JSON (irVersion 1) aligned with md_generator.codeflow.models.ir_cfg. */
final class CodeflowIrEmitter
{
    private int $budget;

    public function __construct(
        private Standard $pp,
        int $maxStmts = 4000,
    ) {
        $this->budget = $maxStmts;
    }

    /** @param array<int, Node\Stmt>|null $stmts */
    public function stmtsToIr(?array $stmts): array
    {
        if ($stmts === null) {
            return [];
        }
        $out = [];
        foreach ($stmts as $st) {
            if ($this->budget <= 0) {
                break;
            }
            foreach ($this->stmtToIr($st) as $row) {
                $out[] = $row;
            }
        }

        return $out;
    }

    /** @return list<array<string,mixed>> */
    private function stmtToIr(Node $st): array
    {
        if ($st instanceof If_) {
            return $this->ifChainToIr($st);
        }
        if ($st instanceof While_) {
            if ($this->budget <= 0) {
                return [];
            }
            $this->budget--;
            $cond = $this->exprCond($st->cond);

            return [[
                'kind' => 'LOOP',
                'condition' => $cond,
                'body' => $this->stmtsToIr($st->stmts),
                'line' => $st->getStartLine(),
            ]];
        }
        if ($st instanceof Do_) {
            if ($this->budget <= 0) {
                return [];
            }
            $this->budget--;
            $cond = $this->exprCond($st->cond);

            return [[
                'kind' => 'LOOP',
                'condition' => 'do-while ' . $cond,
                'body' => $this->stmtsToIr($st->stmts),
                'line' => $st->getStartLine(),
            ]];
        }
        if ($st instanceof For_) {
            if ($this->budget <= 0) {
                return [];
            }
            $this->budget--;

            return [[
                'kind' => 'LOOP',
                'condition' => 'for',
                'body' => $this->stmtsToIr($st->stmts),
                'line' => $st->getStartLine(),
            ]];
        }
        if ($st instanceof Foreach_) {
            if ($this->budget <= 0) {
                return [];
            }
            $this->budget--;

            return [[
                'kind' => 'LOOP',
                'condition' => 'foreach',
                'body' => $this->stmtsToIr($st->stmts),
                'line' => $st->getStartLine(),
            ]];
        }
        if ($st instanceof Switch_) {
            if ($this->budget <= 0) {
                return [];
            }
            $this->budget--;
            $disc = $this->exprCond($st->cond);
            $cases = [];
            foreach ($st->cases as $case) {
                if (! $case instanceof Case_) {
                    continue;
                }
                $lab = 'default:';
                if ($case->cond !== null) {
                    $c = trim(str_replace("\n", ' ', $this->pp->prettyPrintExpr($case->cond)));
                    if (strlen($c) > 120) {
                        $c = substr($c, 0, 117) . '…';
                    }
                    $lab = 'case ' . $c;
                }
                $cases[] = [
                    'label' => $lab,
                    'body' => $this->stmtsToIr($case->stmts),
                ];
            }

            return [[
                'kind' => 'SWITCH',
                'condition' => $disc,
                'cases' => $cases,
                'line' => $st->getStartLine(),
            ]];
        }
        if ($st instanceof Try_) {
            return $this->tryToIr($st);
        }
        if ($st instanceof Return_) {
            if ($this->budget <= 0) {
                return [];
            }
            $this->budget--;
            $lbl = 'return';
            if ($st->expr !== null) {
                $e = trim(str_replace("\n", ' ', $this->pp->prettyPrintExpr($st->expr)));
                if (strlen($e) > 120) {
                    $e = substr($e, 0, 117) . '…';
                }
                $lbl = 'return ' . $e;
            }

            return [['kind' => 'RETURN', 'label' => $lbl, 'line' => $st->getStartLine()]];
        }
        if ($st instanceof Break_) {
            if ($this->budget <= 0) {
                return [];
            }
            $this->budget--;

            return [['kind' => 'BREAK', 'line' => $st->getStartLine()]];
        }
        if ($st instanceof Continue_) {
            if ($this->budget <= 0) {
                return [];
            }
            $this->budget--;

            return [['kind' => 'CONTINUE', 'line' => $st->getStartLine()]];
        }
        if ($st instanceof Expression) {
            $ex = $st->expr;
            if ($ex instanceof FuncCall || $ex instanceof MethodCall || $ex instanceof StaticCall) {
                if ($this->budget <= 0) {
                    return [];
                }
                $this->budget--;
                $callee = $this->callCallee($ex);

                return [['kind' => 'CALL', 'target' => $callee, 'label' => 'call', 'line' => $st->getStartLine()]];
            }
            if ($this->budget <= 0) {
                return [];
            }
            $this->budget--;
            $t = trim(str_replace("\n", ' ', $this->pp->prettyPrintExpr($ex)));
            if (strlen($t) > 120) {
                $t = substr($t, 0, 117) . '…';
            }

            return [['kind' => 'STATEMENT', 'label' => $t, 'line' => $st->getStartLine()]];
        }
        if ($st instanceof Throw_) {
            if ($this->budget <= 0) {
                return [];
            }
            $this->budget--;
            $t = trim(str_replace("\n", ' ', $this->pp->prettyPrintExpr($st->expr)));
            if (strlen($t) > 120) {
                $t = substr($t, 0, 117) . '…';
            }

            return [['kind' => 'STATEMENT', 'label' => 'throw ' . $t, 'line' => $st->getStartLine()]];
        }
        if ($this->budget <= 0) {
            return [];
        }
        $this->budget--;

        return [['kind' => 'STATEMENT', 'label' => $st->getType(), 'line' => $st->getStartLine()]];
    }

    /** @return list<array<string,mixed>> */
    private function ifChainToIr(If_ $node): array
    {
        if ($this->budget <= 0) {
            return [];
        }
        $this->budget--;
        $cond = trim(str_replace("\n", ' ', $this->pp->prettyPrintExpr($node->cond)));
        if (strlen($cond) > 120) {
            $cond = substr($cond, 0, 117) . '…';
        }
        $then = $this->stmtsToIr($node->stmts);
        $elseBody = [];
        if ($node->else !== null) {
            $elseBody = $this->stmtsToIr($node->else->stmts);
        } elseif ($node->elseifs !== []) {
            $first = $node->elseifs[0];
            $rest = array_slice($node->elseifs, 1);
            $nested = new If_($first->cond, $first->stmts, $rest, $node->else);
            $elseBody = $this->ifChainToIr($nested);
        }

        return [[
            'kind' => 'IF',
            'condition' => $cond,
            'body' => $then,
            'else_body' => $elseBody,
            'line' => $node->getStartLine(),
        ]];
    }

    /** @return list<array<string,mixed>> */
    private function tryToIr(Try_ $node): array
    {
        if ($this->budget <= 0) {
            return [];
        }
        $this->budget--;
        $tryBody = $this->stmtsToIr($node->stmts);
        $cases = [];
        foreach ($node->catches as $catch) {
            if (! $catch instanceof Catch_) {
                continue;
            }
            $types = [];
            foreach ($catch->types as $t) {
                $types[] = $t->toString();
            }
            $lab = 'catch ' . implode('|', $types);
            $cases[] = [
                'label' => $lab,
                'body' => $this->stmtsToIr($catch->stmts),
            ];
        }
        $fin = [];
        if ($node->finally !== null) {
            $fin = $this->stmtsToIr($node->finally->stmts);
        }

        return [[
            'kind' => 'TRY',
            'body' => $tryBody,
            'cases' => $cases,
            'else_body' => $fin,
            'line' => $node->getStartLine(),
        ]];
    }

    private function exprCond(Node\Expr $e): string
    {
        $cond = trim(str_replace("\n", ' ', $this->pp->prettyPrintExpr($e)));
        if (strlen($cond) > 120) {
            $cond = substr($cond, 0, 117) . '…';
        }

        return $cond;
    }

    private function callCallee(FuncCall|MethodCall|StaticCall $node): string
    {
        if ($node instanceof FuncCall) {
            $n = $node->name;
            if ($n instanceof Node\Name) {
                return $n->toString();
            }

            return 'call';
        }
        if ($node instanceof MethodCall) {
            return (string) $node->name->name;
        }

        return (string) $node->name->name;
    }
}

final class DumpVisitor extends NodeVisitorAbstract
{
    /** @var list<string> */
    private array $classStack = [];

    /** @var list<string> */
    private array $controlStack = [];

    /** @var list<array<string,mixed>> */
    private array $fnStack = [];

    /** @var list<array<string,mixed>> */
    public array $completed = [];

    private Standard $pp;

    public function __construct(
        private string $fileKey,
        private CodeflowIrEmitter $ir,
    ) {
        $this->pp = new Standard();
    }

    public function enterNode(Node $node)
    {
        if ($node instanceof Class_) {
            $this->classStack[] = (string) $node->name->name;
        } elseif ($node instanceof Function_) {
            $id = $this->fileKey . '::' . (string) $node->name->name;
            $this->fnStack[] = ['id' => $id, 'calls' => [], 'rules' => [], 'branches' => []];
        } elseif ($node instanceof ClassMethod) {
            $cls = $this->classStack[count($this->classStack) - 1] ?? 'anon';
            $id = $this->fileKey . '::' . $cls . '.' . (string) $node->name->name;
            $this->fnStack[] = ['id' => $id, 'calls' => [], 'rules' => [], 'branches' => []];
        } elseif ($node instanceof If_) {
            $cond = trim(str_replace("\n", ' ', $this->pp->prettyPrintExpr($node->cond)));
            if (strlen($cond) > 120) {
                $cond = substr($cond, 0, 117) . '…';
            }
            if ($this->fnStack !== []) {
                $ix = count($this->fnStack) - 1;
                $this->fnStack[$ix]['branches'][] = [
                    'callerId' => $this->fnStack[$ix]['id'],
                    'kind' => 'if',
                    'label' => $cond,
                    'line' => $node->getStartLine(),
                ];
            }
            $this->controlStack[] = $cond;
        } elseif ($node instanceof Case_) {
            $lab = 'default:';
            if ($node->cond !== null) {
                $c = trim(str_replace("\n", ' ', $this->pp->prettyPrintExpr($node->cond)));
                if (strlen($c) > 120) {
                    $c = substr($c, 0, 117) . '…';
                }
                $lab = 'case ' . $c;
            }
            if ($this->fnStack !== []) {
                $ix = count($this->fnStack) - 1;
                $this->fnStack[$ix]['branches'][] = [
                    'callerId' => $this->fnStack[$ix]['id'],
                    'kind' => 'switch',
                    'label' => $lab,
                    'line' => $node->getStartLine(),
                ];
            }
            $this->controlStack[] = $lab;
        } elseif ($node instanceof Throw_) {
            if ($this->fnStack === []) {
                return null;
            }
            $caller = $this->fnStack[count($this->fnStack) - 1]['id'];
            $det = trim(str_replace("\n", ' ', $this->pp->prettyPrintExpr($node->expr)));
            if (strlen($det) > 200) {
                $det = substr($det, 0, 197) . '…';
            }
            $this->fnStack[count($this->fnStack) - 1]['rules'][] = [
                'line' => $node->getStartLine(),
                'title' => 'Throw',
                'detail' => $det,
                'symbolId' => $caller,
            ];
        } elseif ($node instanceof FuncCall || $node instanceof MethodCall || $node instanceof StaticCall) {
            if ($this->fnStack === []) {
                return null;
            }
            $caller = $this->fnStack[count($this->fnStack) - 1]['id'];
            $callee = 'unknown';
            if ($node instanceof FuncCall) {
                $n = $node->name;
                if ($n instanceof Node\Name) {
                    $callee = $n->toString();
                }
            } elseif ($node instanceof MethodCall) {
                $callee = (string) $node->name->name;
            } elseif ($node instanceof StaticCall) {
                $callee = (string) $node->name->name;
            }
            $row = [
                'caller' => $caller,
                'callee' => $callee,
                'line' => $node->getStartLine(),
            ];
            if ($this->controlStack !== []) {
                $row['condition'] = $this->controlStack[count($this->controlStack) - 1];
            }
            $this->fnStack[count($this->fnStack) - 1]['calls'][] = $row;
        }

        return null;
    }

    public function leaveNode(Node $node)
    {
        if ($node instanceof Class_) {
            array_pop($this->classStack);
        } elseif ($node instanceof Function_ || $node instanceof ClassMethod) {
            $top = array_pop($this->fnStack);
            if ($top !== null) {
                $top['body'] = $this->ir->stmtsToIr($node->stmts);
                $this->completed[] = $top;
            }
        } elseif ($node instanceof If_) {
            array_pop($this->controlStack);
        } elseif ($node instanceof Case_) {
            array_pop($this->controlStack);
        }

        return null;
    }
}

$path = $argv[1];
$fileKey = $argc >= 3 ? $argv[2] : $path;
$code = file_get_contents($path);
if ($code === false) {
    echo json_encode(['error' => 'cannot read file'], JSON_UNESCAPED_SLASHES) . "\n";
    exit(1);
}

$parser = (new ParserFactory())->createForNewestSupportedVersion();
try {
    $ast = $parser->parse($code);
} catch (Error $e) {
    echo json_encode(['error' => $e->getMessage()], JSON_UNESCAPED_SLASHES) . "\n";
    exit(1);
}

$ppIr = new Standard();
$irEmitter = new CodeflowIrEmitter($ppIr);
$visitor = new DumpVisitor($fileKey, $irEmitter);
$trav = new NodeTraverser();
$trav->addVisitor($visitor);
$trav->traverse($ast);

echo json_encode(
    ['irVersion' => 1, 'file' => $path, 'funcs' => $visitor->completed],
    JSON_UNESCAPED_SLASHES | JSON_PRETTY_PRINT,
) . "\n";
