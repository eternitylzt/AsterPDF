"""Markdown math/layout workflows, without a browser or system printer."""
from pathlib import Path
import pymupdf as fitz
from PySide6 import QtPrintSupport
from asterpdf.markdown_import import prepare,render
from test_practical_ui import ui


def test_math_code_tables_and_vector_pdf_without_printer(ui,tmp_path,monkeypatch):
    def no_printer(*args,**kwargs):raise AssertionError('Markdown contacted the printer subsystem')
    monkeypatch.setattr(QtPrintSupport,'QPrinter',no_printer)
    source=tmp_path/'math.md'
    source.write_text(r'''# Math document

Inline $Q_\perp$ and $\nabla\times\vec B$.

$$
T=\int_0^1 \frac{x^2}{1+x^2}\,dx
$$

```math
\begin{pmatrix}a&b\\c&d\end{pmatrix}
```

- Parent
  - Nested item

    ```sh
    echo "$PATH" # $not_math$
    ```

| Input | Result |
|---|---|
| value | $\frac{1}{x^{2/7}}$ |

https://example.org
''',encoding='utf8')
    data=prepare(source)
    assert not data[2] and len(data[1])==5
    assert '$not_math$' in data[0] and '<table' in data[0] and '<pre>' in data[0]
    assert '<a href="https://example.org"' in data[0]
    assert all(b'<path' in value for value in data[1].values())
    out=tmp_path/'math.pdf';render(source,out,data)
    with fitz.open(out) as pdf:
        assert len(pdf)==1 and len(pdf[0].get_drawings())>30
        assert not pdf[0].get_images()  # Formulae remain vector paths in saved PDF.
        assert any(link.get('uri')=='https://example.org' for link in pdf[0].get_links())
        if ui[0].platformName()!='offscreen':assert 'Nested item' in pdf[0].get_text()


def test_math_errors_visible_and_code_dollars_preserved(tmp_path):
    source=tmp_path/'mixed.md';source.write_text(r'`$PATH` and $\notARealCommand{x}$ then $\frac{a}{b}$.',encoding='utf8')
    html,resources,errors=prepare(source)
    assert len(errors)==1 and '[Formula:' in html and '<code>$PATH</code>' in html
    assert len(resources)==1


def test_open_math_markdown_background_and_save(ui,tmp_path,monkeypatch):
    app,w,t,pump=ui
    def no_printer(*args,**kwargs):raise AssertionError('Unexpected printer access')
    monkeypatch.setattr(QtPrintSupport,'QPrinter',no_printer)
    source=tmp_path/'nested.md'
    source.write_text(r'# Worker import'+'\n\n'+r'$v=\dfrac{25}{f^{2/7}}\left(5-\exp(1-(x/4)^2)\right)$',encoding='utf8')
    w.open_file(source);pump(lambda:not w.opening and not w.queue.jobs)
    tab=w.current();assert tab.document.original==str(source.resolve())
    saved=tmp_path/'saved.pdf';tab.document.save(saved)
    with fitz.open(saved) as pdf:
        assert len(pdf[0].get_drawings())>25 and not pdf[0].get_images()
        if app.platformName()!='offscreen':assert '[Formula:' not in pdf[0].get_text()


def test_plain_markdown_does_not_start_math_runtime(tmp_path,monkeypatch):
    import quickjs
    monkeypatch.setattr(quickjs,'Context',lambda:(_ for _ in ()).throw(AssertionError('Unneeded math runtime')))
    source=tmp_path/'plain.md';source.write_text('# Plain\n\n- item\n  - child\n\n```sh\necho "$HOME"\n```\n',encoding='utf8')
    html,resources,errors=prepare(source)
    assert not errors and not resources and html.count('<ul>')==2 and '$HOME' in html
