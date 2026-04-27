package main

import (
	"go/ast"
	"testing"
)

func TestFuncID(t *testing.T) {
	if got := funcID("pkg/a.go", "", "main"); got != "pkg/a.go::main" {
		t.Fatalf("funcID module: got %q", got)
	}
	if got := funcID("pkg/a.go", "T", "M"); got != "pkg/a.go::T.M" {
		t.Fatalf("funcID method: got %q", got)
	}
}

func TestCalleeString_selector(t *testing.T) {
	ce := &ast.CallExpr{
		Fun: &ast.SelectorExpr{
			X:   &ast.Ident{Name: "fmt"},
			Sel: &ast.Ident{Name: "Println"},
		},
	}
	if got := calleeString(ce); got != "fmt.Println" {
		t.Fatalf("got %q", got)
	}
}

func TestCalleeString_ident(t *testing.T) {
	ce := &ast.CallExpr{Fun: &ast.Ident{Name: "foo"}}
	if got := calleeString(ce); got != "foo" {
		t.Fatalf("got %q", got)
	}
}
