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
use PhpParser\Node\Stmt\Case_;
use PhpParser\Node\Stmt\Class_;
use PhpParser\Node\Stmt\ClassMethod;
use PhpParser\Node\Stmt\Function_;
use PhpParser\Node\Stmt\If_;
use PhpParser\Node\Stmt\Throw_;
use PhpParser\NodeTraverser;
use PhpParser\NodeVisitorAbstract;
use PhpParser\ParserFactory;
use PhpParser\PrettyPrinter\Standard;

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

final class DumpVisitor extends NodeVisitorAbstract
{
    /** @var list<string> */
    private array $classStack = [];

    /** @var list<string> */
    private array $controlStack = [];

    /** @var list<array{id:string,calls:list<array<string,mixed>>,rules:list<array<string,mixed>>,branches:list<array<string,mixed>>}> */
    private array $fnStack = [];

    /** @var list<array{id:string,calls:list<array<string,mixed>>,rules:list<array<string,mixed>>,branches:list<array<string,mixed>>}> */
    public array $completed = [];

    private Standard $pp;

    public function __construct(private string $fileKey)
    {
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

$visitor = new DumpVisitor($fileKey);
$trav = new NodeTraverser();
$trav->addVisitor($visitor);
$trav->traverse($ast);

echo json_encode(['file' => $path, 'funcs' => $visitor->completed], JSON_UNESCAPED_SLASHES | JSON_PRETTY_PRINT) . "\n";
