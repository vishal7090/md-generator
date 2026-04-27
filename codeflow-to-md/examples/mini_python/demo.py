"""Sample flow: ClassA.a → b → branch → c / B methods."""

from __future__ import annotations


class ClassB:
    def method1(self) -> None:
        pass

    def method2(self) -> None:
        pass


class ClassA:
    def a(self) -> None:
        self.b()

    def b(self, cond1: bool = False, cond2: bool = False) -> None:
        if cond1:
            self.c()
        elif cond2:
            ClassB().method1()
        else:
            ClassB().method2()

    def c(self) -> None:
        pass


def main() -> None:
    ClassA().a()


if __name__ == "__main__":
    main()
