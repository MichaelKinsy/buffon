# SPDX-License-Identifier: Apache-2.0
"""The KaTeX source of every formula the dashboard shows (method, metric pages, glossary).
KaTeX renders them once at build time (mathtex.py); a comparison's own numbers are shown beside them in plain text. The page carries no math script.
\\T{key}{...} colours a term like its chart mark: x the harness, y Pi, ci the interval, f the noise floor, r the ratio."""
MEDIAN = r"\widetilde{x} = \operatorname{median}(x_1, \dots, x_n)"
RATIO = r"R = \frac{\T{x}{\med(x)}}{\T{y}{\med(y)}}"
INTERVAL = r"\T{ci}{[L,\,U]} = \bigl[\,q_{0.025}(R^{*}),\ q_{0.975}(R^{*})\,\bigr]"
FLOOR = r"\T{f}{f} = \max\bigl(\lvert\ln R_{AA}\rvert,\ \ln U_{AA},\ -\ln L_{AA}\bigr)"
MDE = r"\mathrm{MDE} = \exp\!\Bigl(\bigl(z_{0.975} + z_{0.8}\bigr)\,\frac{s_{\ln}}{\sqrt{n}}\Bigr) - 1"

