// Codeflow: dump Go call graph edges as JSON for Python consumer.
package main

import (
	"encoding/json"
	"fmt"
	"go/ast"
	"go/parser"
	"go/token"
	"os"
)

type call struct {
	Caller string `json:"caller"`
	Callee string `json:"callee"`
	Line   int    `json:"line"`
}

type fn struct {
	ID    string  `json:"id"`
	Calls []call  `json:"calls"`
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
		entry := fn{ID: id, Calls: nil}
		ast.Inspect(fd.Body, func(n ast.Node) bool {
			ce, ok := n.(*ast.CallExpr)
			if !ok {
				return true
			}
			pos := fset.Position(ce.Pos())
			entry.Calls = append(entry.Calls, call{
				Caller: id,
				Callee: calleeString(ce),
				Line:   pos.Line,
			})
			return true
		})
		doc.Funcs = append(doc.Funcs, entry)
	}
	enc := json.NewEncoder(os.Stdout)
	enc.SetIndent("", "  ")
	if err := enc.Encode(doc); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
