"""Small deterministic SVG figures for the report, written by hand so the analysis needs no plotting package.

One kind of figure: labelled point estimates with 95 percent intervals on a shared horizontal axis, optionally with shaded equivalence
margins around zero. The same input always gives the same bytes. Colours come from CSS variables with fallbacks, so the figure follows a
light or dark page when it is inlined, and reads well on white when it is opened alone.
"""
from xml.sax.saxutils import escape

WIDTH = 720
ROW = 30
LEFT = 230
RIGHT = 40
TOP = 56
BOTTOM = 48
STYLES = {
    'confirmatory': ('var(--fig-ink, #1f4e79)', 'none'),
    'exploratory': ('var(--fig-accent, #b35900)', '4 3'),
    'descriptive': ('var(--fig-muted, #6b6b6b)', '2 3'),
}


def _fmt(value):
    """A tick label with as few decimals as the value needs, up to four (0.02 stays 0.02, 20.0 is 20)."""
    text = ('%.4f' % value).rstrip('0').rstrip('.')
    return '0' if text in ('-0', '') else text


def interval_plot(title, axis_label, items, lo, hi, ticks, margins=(), note=None):
    """`items`: (label, estimate, low, high, style) with style a key of STYLES; low/high may be None for a point without an interval."""
    height = TOP + ROW * len(items) + BOTTOM + (18 if note else 0)
    plot_w = WIDTH - LEFT - RIGHT

    def x(v):
        return LEFT + (v - lo) / (hi - lo) * plot_w

    out = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" height="%d" role="img" aria-label="%s">'
           % (WIDTH, height, WIDTH, height, escape(title, {'"': '&quot;'})),
           '<style>text{font-family:system-ui,-apple-system,"Segoe UI",sans-serif;font-size:13px;fill:var(--fig-text,#222)}'
           '.t{font-size:15px;font-weight:600}.s{font-size:11px;fill:var(--fig-muted,#6b6b6b)}</style>',
           '<rect x="0" y="0" width="%d" height="%d" fill="var(--fig-bg,#ffffff)"/>' % (WIDTH, height),
           '<text class="t" x="16" y="26">%s</text>' % escape(title)]
    bottom = TOP + ROW * len(items)
    for margin, shade in margins:
        out.append('<rect x="%.1f" y="%d" width="%.1f" height="%d" fill="var(--fig-band,#1f4e79)" fill-opacity="%s"/>'
                   % (x(-margin), TOP - 8, x(margin) - x(-margin), bottom - TOP + 8, shade))
    for t in ticks:
        out.append('<line x1="%.1f" y1="%d" x2="%.1f" y2="%d" stroke="var(--fig-grid,#d0d0d0)" stroke-width="1"/>'
                   % (x(t), TOP - 8, x(t), bottom))
        out.append('<text class="s" x="%.1f" y="%d" text-anchor="middle">%s</text>' % (x(t), bottom + 16, _fmt(t)))
    out.append('<text class="s" x="%.1f" y="%d" text-anchor="middle">%s</text>' % (LEFT + plot_w / 2, bottom + 34, escape(axis_label)))
    for i, (label, est, low, high, style) in enumerate(items):
        colour, dash = STYLES[style]
        y = TOP + ROW * i + ROW / 2 - 4
        out.append('<text x="%d" y="%.1f" text-anchor="end" dominant-baseline="middle">%s</text>' % (LEFT - 12, y, escape(label)))
        if low is not None and high is not None:
            out.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="2.5" stroke-dasharray="%s"/>'
                       % (x(low), y, x(high), y, colour, dash))
        out.append('<circle cx="%.1f" cy="%.1f" r="5" fill="%s"/>' % (x(est), y, colour))
    if note:
        out.append('<text class="s" x="16" y="%d">%s</text>' % (height - 10, escape(note)))
    out.append('</svg>')
    return '\n'.join(out) + '\n'
