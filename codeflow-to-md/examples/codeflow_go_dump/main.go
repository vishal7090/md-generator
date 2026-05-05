// Codeflow: dump Go call graph edges and CFG-oriented IR (JSON) for Python consumer.
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

const irVersion = 1

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

type irCaseJSON struct {
	Label string       `json:"label"`
	Body  []irStmtJSON `json:"body"`
}

type irStmtJSON struct {
	Kind      string         `json:"kind"`
	Condition string         `json:"condition,omitempty"`
	Body      []irStmtJSON   `json:"body,omitempty"`
	ElseBody  []irStmtJSON   `json:"else_body,omitempty"`
	Cases     []irCaseJSON   `json:"cases,omitempty"`
	Target    string         `json:"target,omitempty"`
	Label     string         `json:"label,omitempty"`
	Line      int            `json:"line,omitempty"`
}

type fn struct {
	ID        string       `json:"id"`
	StartLine int          `json:"startLine"`
	EndLine   int          `json:"endLine"`
	Calls     []call       `json:"calls"`
	Rules     []ruleOut    `json:"rules"`
	Body      []irStmtJSON `json:"body,omitempty"`
}

type outDoc struct {
	IrVersion int    `json:"irVersion"`
	File      string `json:"file"`
	Funcs     []fn   `json:"funcs"`
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

func takeBudget(budget *int) bool {
	if budget == nil {
		return true
	}
	if *budget <= 0 {
		return false
	}
	*budget--
	return true
}

func convertBlock(fset *token.FileSet, list []ast.Stmt, budget *int) []irStmtJSON {
	var out []irStmtJSON
	for _, st := range list {
		if budget != nil && *budget <= 0 {
			break
		}
		out = append(out, convertStmt(fset, st, budget)...)
	}
	return out
}

func convertStmt(fset *token.FileSet, st ast.Stmt, budget *int) []irStmtJSON {
	if st == nil {
		return nil
	}
	switch s := st.(type) {
	case *ast.LabeledStmt:
		return convertStmt(fset, s.Stmt, budget)
	case *ast.BlockStmt:
		return convertBlock(fset, s.List, budget)
	case *ast.IfStmt:
		if !takeBudget(budget) {
			return nil
		}
		cond := trim(exprString(s.Cond), 120)
		pos := fset.Position(s.Pos())
		thenBody := convertBlock(fset, stmtListFromBody(s.Body), budget)
		var elseBody []irStmtJSON
		if s.Else != nil {
			if el, ok := s.Else.(*ast.BlockStmt); ok {
				elseBody = convertBlock(fset, el.List, budget)
			} else if elif, ok := s.Else.(*ast.IfStmt); ok {
				elseBody = convertStmt(fset, elif, budget)
			}
		}
		return []irStmtJSON{{
			Kind: "IF", Condition: cond, Body: thenBody, ElseBody: elseBody, Line: pos.Line,
		}}
	case *ast.ForStmt:
		if !takeBudget(budget) {
			return nil
		}
		parts := []string{}
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
		pos := fset.Position(s.Pos())
		body := convertBlock(fset, stmtListFromBody(s.Body), budget)
		return []irStmtJSON{{Kind: "LOOP", Condition: lab, Body: body, Line: pos.Line}}
	case *ast.RangeStmt:
		if !takeBudget(budget) {
			return nil
		}
		pos := fset.Position(s.Pos())
		body := convertBlock(fset, stmtListFromBody(s.Body), budget)
		return []irStmtJSON{{Kind: "LOOP", Condition: "range", Body: body, Line: pos.Line}}
	case *ast.SwitchStmt:
		if !takeBudget(budget) {
			return nil
		}
		disc := "switch"
		if s.Tag != nil {
			disc = trim(exprString(s.Tag), 120)
		}
		var cases []irCaseJSON
		if s.Body != nil {
			for _, c := range s.Body.List {
				cc, ok := c.(*ast.CaseClause)
				if !ok {
					continue
				}
				lab := "default:"
				if len(cc.List) > 0 {
					parts := make([]string, 0, len(cc.List))
					for _, e := range cc.List {
						parts = append(parts, exprString(e))
					}
					lab = "case " + strings.Join(parts, ", ")
				}
				body := convertBlock(fset, cc.Body, budget)
				cases = append(cases, irCaseJSON{Label: trim(lab, 120), Body: body})
			}
		}
		pos := fset.Position(s.Pos())
		return []irStmtJSON{{Kind: "SWITCH", Condition: disc, Cases: cases, Line: pos.Line}}
	case *ast.TypeSwitchStmt:
		if !takeBudget(budget) {
			return nil
		}
		disc := "type switch"
		if a, ok := s.Assign.(*ast.AssignStmt); ok && len(a.Rhs) > 0 {
			disc = trim(exprString(a.Rhs[0]), 120)
		}
		var cases []irCaseJSON
		if s.Body != nil {
			for _, c := range s.Body.List {
				cc, ok := c.(*ast.CaseClause)
				if !ok {
					continue
				}
				lab := "default:"
				if len(cc.List) > 0 {
					parts := make([]string, 0, len(cc.List))
					for _, e := range cc.List {
						parts = append(parts, exprString(e))
					}
					lab = "case " + strings.Join(parts, ", ")
				}
				body := convertBlock(fset, cc.Body, budget)
				cases = append(cases, irCaseJSON{Label: trim(lab, 120), Body: body})
			}
		}
		pos := fset.Position(s.Pos())
		return []irStmtJSON{{Kind: "SWITCH", Condition: disc, Cases: cases, Line: pos.Line}}
	case *ast.SelectStmt:
		if !takeBudget(budget) {
			return nil
		}
		var inner []irStmtJSON
		if s.Body != nil {
			for _, cl := range s.Body.List {
				comm, ok := cl.(*ast.CommClause)
				if !ok {
					continue
				}
				inner = append(inner, convertBlock(fset, comm.Body, budget)...)
			}
		}
		pos := fset.Position(s.Pos())
		return []irStmtJSON{{Kind: "LOOP", Condition: "select", Body: inner, Line: pos.Line}}
	case *ast.ExprStmt:
		if ce, ok := s.X.(*ast.CallExpr); ok {
			if !takeBudget(budget) {
				return nil
			}
			pos := fset.Position(ce.Pos())
			return []irStmtJSON{{Kind: "CALL", Target: calleeString(ce), Label: "call", Line: pos.Line}}
		}
		if !takeBudget(budget) {
			return nil
		}
		pos := fset.Position(s.Pos())
		return []irStmtJSON{{Kind: "STATEMENT", Label: trim(exprString(s.X), 120), Line: pos.Line}}
	case *ast.GoStmt:
		if s.Call == nil || !takeBudget(budget) {
			return nil
		}
		pos := fset.Position(s.Call.Pos())
		return []irStmtJSON{{Kind: "CALL", Target: "go " + calleeString(s.Call), Label: "go", Line: pos.Line}}
	case *ast.DeferStmt:
		if s.Call == nil || !takeBudget(budget) {
			return nil
		}
		pos := fset.Position(s.Call.Pos())
		return []irStmtJSON{{Kind: "CALL", Target: "defer " + calleeString(s.Call), Label: "defer", Line: pos.Line}}
	case *ast.AssignStmt:
		if len(s.Rhs) == 1 {
			if ce, ok := s.Rhs[0].(*ast.CallExpr); ok {
				if !takeBudget(budget) {
					return nil
				}
				pos := fset.Position(ce.Pos())
				return []irStmtJSON{{Kind: "CALL", Target: calleeString(ce), Label: "call", Line: pos.Line}}
			}
		}
		if !takeBudget(budget) {
			return nil
		}
		pos := fset.Position(s.Pos())
		return []irStmtJSON{{Kind: "STATEMENT", Label: "assign", Line: pos.Line}}
	case *ast.ReturnStmt:
		if !takeBudget(budget) {
			return nil
		}
		pos := fset.Position(s.Pos())
		lbl := "return"
		if s.Results != nil && len(s.Results) > 0 {
			parts := make([]string, 0, len(s.Results))
			for _, e := range s.Results {
				parts = append(parts, exprString(e))
			}
			lbl = trim("return "+strings.Join(parts, ", "), 120)
		}
		return []irStmtJSON{{Kind: "RETURN", Label: lbl, Line: pos.Line}}
	case *ast.BranchStmt:
		if !takeBudget(budget) {
			return nil
		}
		pos := fset.Position(s.Pos())
		switch s.Tok {
		case token.BREAK:
			return []irStmtJSON{{Kind: "BREAK", Line: pos.Line}}
		case token.CONTINUE:
			return []irStmtJSON{{Kind: "CONTINUE", Line: pos.Line}}
		default:
			return []irStmtJSON{{Kind: "STATEMENT", Label: s.Tok.String(), Line: pos.Line}}
		}
	default:
		if !takeBudget(budget) {
			return nil
		}
		pos := fset.Position(st.Pos())
		return []irStmtJSON{{Kind: "STATEMENT", Label: fmt.Sprintf("%T", st), Line: pos.Line}}
	}
}

func stmtListFromBody(b *ast.BlockStmt) []ast.Stmt {
	if b == nil {
		return nil
	}
	return b.List
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
	doc := outDoc{IrVersion: irVersion, File: fp, Funcs: nil}

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
		budget := 4000
		entry.Body = convertBlock(fset, fd.Body.List, &budget)
		doc.Funcs = append(doc.Funcs, entry)
	}
	enc := json.NewEncoder(os.Stdout)
	enc.SetIndent("", "  ")
	if err := enc.Encode(doc); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
