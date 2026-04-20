from __future__ import annotations

from bs4 import BeautifulSoup


def extract_main_content(html: str) -> str:
    """
    Strip chrome (script/style/nav/footer/header), then prefer main/article/role=main.
    Returns HTML string of the chosen subtree (or body).
    """
    soup = BeautifulSoup(html, "lxml")
    for tag in soup.find_all(["script", "style", "noscript"]):
        tag.decompose()
    for tag in soup.find_all(["nav", "footer", "header"]):
        tag.decompose()

    root = (
        soup.find("main")
        or soup.select_one('[role="main"]')
        or soup.find("article")
        or soup.find("body")
        or soup
    )
    return str(root)
