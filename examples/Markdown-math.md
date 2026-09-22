# AsterPDF · Markdown & mathematics

Inline mathematics: $Q_\perp$, $\nabla\times\vec B$, and $\alpha^2+\beta^2=1$.

## Equations

$$
I=\int_0^1 \frac{x^2}{1+x^2}\,\mathrm{d}x
$$

```math
A=\begin{pmatrix}a&b\\c&d\end{pmatrix}
```

## Tables and nested code

| Quantity | Expression |
|---|---|
| Fraction | $\frac{a+b}{c+d}$ |
| Vector | $\vec r=(x,y,z)$ |

- First step
  - A nested explanation

    ```python
    label = "$this_is_code$"
    print(label)
    ```

- [x] Formulae work offline and remain vector paths in exported PDF.
- [x] Code keeps its literal dollar signs.

[Project](https://github.com/eternitylzt/AsterPDF)
