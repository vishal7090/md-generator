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
use PhpParser\Node\Stmt\Class_;
use PhpParser\Node\Stmt\ClassMethod;
use PhpParser\Node\Stmt\Function_;
use PhpParser\NodeTraverser;
use PhpParser\NodeVisitorAbstract;
use PhpParser\ParserFactory;

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

    /** @var list<array{id:string,calls:list<array{caller:string,callee:string,line:int}>}> */
    private array $fnStack = [];

    /** @var list<array{id:string,calls:list<array{caller:string,callee:string,line:int}>}> */
    public array $completed = [];

    public function __construct(private string $fileKey)
    {
    }

    public function enterNode(Node $node)
    {
        if ($node instanceof Class_) {
            $this->classStack[] = (string) $node->name->name;
        } elseif ($node instanceof Function_) {
            $id = $this->fileKey . '::' . (string) $node->name->name;
            $this->fnStack[] = ['id' => $id, 'calls' => []];
        } elseif ($node instanceof ClassMethod) {
            $cls = $this->classStack[count($this->classStack) - 1] ?? 'anon';
            $id = $this->fileKey . '::' . $cls . '.' . (string) $node->name->name;
            $this->fnStack[] = ['id' => $id, 'calls' => []];
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
            $this->fnStack[count($this->fnStack) - 1]['calls'][] = [
                'caller' => $caller,
                'callee' => $callee,
                'line' => $node->getStartLine(),
            ];
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
        }
        return null;
    }
}

$visitor = new DumpVisitor($fileKey);
$trav = new NodeTraverser();
$trav->addVisitor($visitor);
$trav->traverse($ast);

echo json_encode(['file' => $path, 'funcs' => $visitor->completed], JSON_UNESCAPED_SLASHES | JSON_PRETTY_PRINT) . "\n";
