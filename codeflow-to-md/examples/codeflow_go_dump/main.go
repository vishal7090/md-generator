// Codeflow: dump Go call graph edges as JSON for Python consumer.
package main

import (
	"encoding/json"
	"fmt"
	"go/ast"
	"go/parser"
	"go/token"
	"os"
	"strings"
)

type call struct {
	Caller    string `json:"caller"`
	Callee    string `json:"callee"`
	Line      int    `json:"line"`
	Condition string `json:"condition,omitempty"`
}

type ruleOut struct {
	Line     int    `json:"line"`
	Title    string `json:"title"`
	Detail   string `json:"detail"`
	SymbolID string `json:"symbolId"`
}

type fn struct {
	ID        string    `json:"id"`
	StartLine int       `json:"startLine"`
	EndLine   int       `json:"endLine"`
	Calls     []call    `json:"calls"`
	Rules     []ruleOut `json:"rules"`
}

type outDoc struct {
	File  string `json:"file"`
	Funcs []fn   `json:"funcs"`
}

func calleeString(e *ast.CallExpr) string {
	switch t := e.Fun.(type) {
	case *ast.SelectorExpr:
		if x, ok := t.X.(*ast.Ident); ok {
			return x.Name + "." + t.Sel.Name
		}
		return "." + t.Sel.Name
	case *ast.Ident:
		return t.Name
	default:
		return "unknown"
	}
}

func recvTypeString(fd *ast.FuncDecl) string {
	if fd.Recv == nil || len(fd.Recv.List) == 0 {
		return ""
	}
	ft := fd.Recv.List[0].Type
	switch x := ft.(type) {
	case *ast.StarExpr:
		if id, ok := x.X.(*ast.Ident); ok {
			return id.Name
		}
	case *ast.Ident:
		return x.Name
	}
	return "recv"
}

func funcID(fileKey, recv, name string) string {
	if recv == "" {
		return fileKey + "::" + name
	}
	return fileKey + "::" + recv + "." + name
}

func exprString(e ast.Expr) string {
	if e == nil {
		return ""
	}
	switch x := e.(type) {
	case *ast.Ident:
		return x.Name
	case *ast.BinaryExpr:
		return exprString(x.X) + " " + x.Op.String() + " " + exprString(x.Y)
	case *ast.ParenExpr:
		return "(" + exprString(x.X) + ")"
	case *ast.BasicLit:
		return x.Value
	case *ast.SelectorExpr:
		return exprString(x.X) + "." + x.Sel.Name
	case *ast.CallExpr:
		return calleeString(x) + "(…)"
	default:
		return "expr"
	}
}

func trim(s string, n int) string {
	s = strings.Join(strings.Fields(s), " ")
	if len(s) <= n {
		return s
	}
	return s[:n-1] + "…"
}

func walkStmtList(
	fset *token.FileSet,
	list []ast.Stmt,
	callerID string,
	condStack []string,
	entry *fn,
) {
	for _, st := range list {
		switch s := st.(type) {
		case *ast.IfStmt:
			lab := trim(exprString(s.Cond), 120)
			ncond := append(condStack, lab)
			if s.Body != nil {
				walkStmtList(fset, s.Body.List, callerID, ncond, entry)
			}
			if s.Else != nil {
				if el, ok := s.Else.(*ast.BlockStmt); ok {
					walkStmtList(fset, el.List, callerID, append(condStack, "else"), entry)
				} else if elIf, ok := s.Else.(*ast.IfStmt); ok {
					walkStmtList(fset, []ast.Stmt{elIf}, callerID, condStack, entry)
				}
			}
		case *ast.SwitchStmt:
			if s.Body != nil {
				for _, c := range s.Body.List {
					if cc, ok := c.(*ast.CaseClause); ok {
						var lab string
						if len(cc.List) == 0 {
							lab = "default:"
						} else {
							parts := make([]string, 0, len(cc.List))
							for _, e := range cc.List {
								parts = append(parts, exprString(e))
							}
							lab = "case " + strings.Join(parts, ", ")
						}
						ncond := append(condStack, trim(lab, 120))
						walkStmtList(fset, cc.Body, callerID, ncond, entry)
					}
				}
			}
		case *ast.ForStmt:
			var parts []string
			if s.Init != nil {
				parts = append(parts, "init")
			}
			if s.Cond != nil {
				parts = append(parts, trim(exprString(s.Cond), 80))
			}
			lab := "for"
			if len(parts) > 0 {
				lab = strings.Join(parts, "; ")
			}
			if s.Body != nil {
				walkStmtList(fset, s.Body.List, callerID, append(condStack, lab), entry)
			}
		case *ast.RangeStmt:
			if s.Body != nil {
				walkStmtList(fset, s.Body.List, callerID, append(condStack, "range"), entry)
			}
		case *ast.ExprStmt:
			if ce, ok := s.X.(*ast.CallExpr); ok {
				pos := fset.Position(ce.Pos())
				c := call{
					Caller: callerID,
					Callee: calleeString(ce),
					Line:   pos.Line,
				}
				if len(condStack) > 0 {
					c.Condition = condStack[len(condStack)-1]
				}
				entry.Calls = append(entry.Calls, c)
			}
		case *ast.GoStmt:
			if s.Call != nil {
				ce := s.Call
				pos := fset.Position(ce.Pos())
				c := call{Caller: callerID, Callee: calleeString(ce), Line: pos.Line}
				if len(condStack) > 0 {
					c.Condition = condStack[len(condStack)-1]
				}
				entry.Calls = append(entry.Calls, c)
			}
		case *ast.DeferStmt:
			if s.Call != nil {
				ce := s.Call
				pos := fset.Position(ce.Pos())
				c := call{Caller: callerID, Callee: calleeString(ce), Line: pos.Line}
				if len(condStack) > 0 {
					c.Condition = condStack[len(condStack)-1]
				}
				entry.Calls = append(entry.Calls, c)
			}
		case *ast.BlockStmt:
			walkStmtList(fset, s.List, callerID, condStack, entry)
		case *ast.AssignStmt:
			if len(s.Rhs) == 1 {
				if ce, ok := s.Rhs[0].(*ast.CallExpr); ok {
					pos := fset.Position(ce.Pos())
					c := call{Caller: callerID, Callee: calleeString(ce), Line: pos.Line}
					if len(condStack) > 0 {
						c.Condition = condStack[len(condStack)-1]
					}
					entry.Calls = append(entry.Calls, c)
				}
			}
		case *ast.ReturnStmt:
			if s.Results != nil && len(s.Results) == 1 {
				if ce, ok := s.Results[0].(*ast.CallExpr); ok {
					pos := fset.Position(ce.Pos())
					c := call{Caller: callerID, Callee: calleeString(ce), Line: pos.Line}
					if len(condStack) > 0 {
						c.Condition = condStack[len(condStack)-1]
					}
					entry.Calls = append(entry.Calls, c)
				}
			}
		}
	}
}

func collectRules(fset *token.FileSet, body *ast.BlockStmt, callerID string, entry *fn) {
	if body == nil {
		return
	}
	ast.Inspect(body, func(n ast.Node) bool {
		switch x := n.(type) {
		case *ast.CallExpr:
			fn := calleeString(x)
			if fn == "panic" || strings.HasSuffix(fn, ".Fatalf") || strings.HasSuffix(fn, ".Fatal") {
				pos := fset.Position(x.Pos())
				det := trim(exprString(x), 200)
				entry.Rules = append(entry.Rules, ruleOut{
					Line:     pos.Line,
					Title:    "Panic / fatal log",
					Detail:   det,
					SymbolID: callerID,
				})
			}
		}
		return true
	})
}

func main() {
	if len(os.Args) < 2 {
		fmt.Fprintln(os.Stderr, "usage: codeflow_go_dump <file.go> [fileKey]")
		os.Exit(2)
	}
	fp := os.Args[1]
	fileKey := fp
	if len(os.Args) >= 3 && os.Args[2] != "" {
		fileKey = os.Args[2]
	}
	fset := token.NewFileSet()
	f, err := parser.ParseFile(fset, fp, nil, parser.ParseComments)
	if err != nil {
		_ = json.NewEncoder(os.Stdout).Encode(map[string]string{"error": err.Error()})
		os.Exit(1)
	}
	doc := outDoc{File: fp, Funcs: nil}

	for _, decl := range f.Decls {
		fd, ok := decl.(*ast.FuncDecl)
		if !ok {
			continue
		}
		if fd.Body == nil {
			continue
		}
		recv := recvTypeString(fd)
		id := funcID(fileKey, recv, fd.Name.Name)
		start := fset.Position(fd.Pos()).Line
		end := fset.Position(fd.End()).Line
		entry := fn{ID: id, StartLine: start, EndLine: end, Calls: nil, Rules: nil}
		walkStmtList(fset, fd.Body.List, id, nil, &entry)
		collectRules(fset, fd.Body, id, &entry)
		doc.Funcs = append(doc.Funcs, entry)
	}
	enc := json.NewEncoder(os.Stdout)
	enc.SetIndent("", "  ")
	if err := enc.Encode(doc); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
