"""
Lifetime Health — Treatment Plan PDF Generator
Requires: pip install reportlab

Usage:
  python generate_pdf.py             # generates sample TKR plan
  python generate_pdf.py --help      # shows usage

In production this will be called by the Node.js server:
  python generate_pdf.py --json '{"patient":...,"plan":...}'
"""
from reportlab.pdfgen import canvas as rc
from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import HexColor, white
from reportlab.lib.units import mm
import json, sys, os

W, H = A4
ML   = 15 * mm
MR   = 15 * mm
CW   = W - ML - MR

C = dict(
    navy1     = HexColor('#0A1838'),   # darkest header
    navy2     = HexColor('#1A2744'),   # primary brand navy
    navy3     = HexColor('#1E2D5A'),   # secondary navy
    blue      = HexColor('#3B6FE8'),   # primary brand blue
    blue2     = HexColor('#2563EB'),   # accent blue
    blue_l    = HexColor('#EEF2FF'),   # light blue surface
    blue_l2   = HexColor('#DBEAFE'),   # lighter blue surface
    blue_pale = HexColor('#F4F6FF'),   # palest blue background
    red       = HexColor('#DC2626'),
    red_l     = HexColor('#FEE2E2'),
    amber     = HexColor('#D97706'),
    green     = HexColor('#16A34A'),
    grey_l    = HexColor('#F4F6FF'),   # tinted with brand blue
    grey1     = HexColor('#1A2744'),   # text = brand navy
    grey2     = HexColor('#475569'),
    grey3     = HexColor('#94A3B8'),
    line      = HexColor('#DBEAFE'),
)

def col(name): return C[name]

def gradient(c, x, y, w, h, top_col, bot_col, steps=50):
    def rgb(color): return color.red, color.green, color.blue
    r1,g1,b1 = rgb(top_col); r2,g2,b2 = rgb(bot_col)
    sh = h / steps
    for i in range(steps):
        t = i / (steps - 1)
        c.setFillColorRGB(r1+(r2-r1)*t, g1+(g2-g1)*t, b1+(b2-b1)*t)
        c.rect(x, y + (steps-1-i)*sh, w, sh+0.5, fill=1, stroke=0)

def fill_rect(c, x, y, w, h, color, radius=0):
    c.setFillColor(color)
    if radius: c.roundRect(x, y, w, h, radius, fill=1, stroke=0)
    else: c.rect(x, y, w, h, fill=1, stroke=0)

def text(c, s, x, y, font='Helvetica', size=9, color=None, align='left'):
    if color: c.setFillColor(color)
    c.setFont(font, size)
    if align == 'right': c.drawRightString(x, y, s)
    elif align == 'center': c.drawCentredString(x, y, s)
    else: c.drawString(x, y, s)

def wrap_text(c, s, x, y, max_width, font='Helvetica', size=8,
              color=None, leading=11, max_lines=2):
    """Word-wrap s into up to max_lines lines. Returns total height used."""
    if color:
        c.setFillColor(color)
    c.setFont(font, size)
    words = s.split()
    wrapped = []
    current = []
    for word in words:
        test_ln = ' '.join(current + [word])
        if c.stringWidth(test_ln, font, size) <= max_width:
            current.append(word)
        else:
            if current:
                wrapped.append(' '.join(current))
            current = [word]
    if current:
        wrapped.append(' '.join(current))
    wrapped = wrapped[:max_lines]
    for i, ln in enumerate(wrapped):
        c.drawString(x, y - i * leading, ln)
    return len(wrapped) * leading

def draw_footer(c, page_num):
    fill_rect(c, 0, 0, W, 11*mm, col('grey_l'))
    c.setStrokeColor(col('line')); c.setLineWidth(0.5); c.line(0, 11*mm, W, 11*mm)
    text(c, 'Lifetime Health  ·  lifetimehealth.in  ·  Confidential — for clinical use only',
         ML, 4*mm, size=6.5, color=col('grey3'))
    text(c, f'Page {page_num}', W-MR, 4*mm, size=6.5, color=col('grey3'), align='right')

PHASE_COLS  = [HexColor('#2563EB'), HexColor('#3B6FE8'), HexColor('#1A2744')]
PHASE_LIGHT = [HexColor('#EEF2FF'), HexColor('#DBEAFE'), HexColor('#EEF2FF')]

# Logo asset — 1557 × 611 px, aspect ratio ≈ 2.55 : 1
LOGO_PATH   = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assets', 'logo.png')
LOGO_ASPECT = 611 / 1557   # height / width


def draw_pain_trajectory(c, y, trajectory):
    """Draw pain recovery trajectory chart. Returns new y position."""
    if not trajectory or len(trajectory) < 2:
        return y

    # Section header
    fill_rect(c, ML, y - 9.5*mm, CW, 9.5*mm, col('blue'), radius=2*mm)
    text(c, 'PAIN RECOVERY TRAJECTORY', ML + 4*mm, y - 9.5*mm + 3.2*mm,
         'Helvetica-Bold', 8.5, white)
    y -= 9.5*mm + 4*mm

    # Chart card
    chart_h = 65*mm
    chart_x = ML + 14*mm
    chart_w = CW - 18*mm
    chart_top = y - 8*mm
    chart_bot = y - chart_h + 12*mm
    ch_h = chart_top - chart_bot

    fill_rect(c, ML, y - chart_h, CW, chart_h, white)
    c.setStrokeColor(col('line'))
    c.setLineWidth(0.5)
    c.rect(ML, y - chart_h, CW, chart_h)

    max_week = max(d.get('week', 0) for d in trajectory) or 1

    def x_scale(week):
        return chart_x + (week / max_week) * chart_w

    def y_scale(val):
        return chart_bot + (val / 10) * ch_h

    # Background zones
    fill_rect(c, chart_x, y_scale(0), chart_w,
              y_scale(4) - y_scale(0), HexColor('#F0FDF4'))
    fill_rect(c, chart_x, y_scale(6), chart_w,
              y_scale(10) - y_scale(6), HexColor('#FEF2F2'))

    # Grid + Y labels
    c.setStrokeColor(col('line'))
    c.setLineWidth(0.3)
    for v in range(0, 11, 2):
        gy = y_scale(v)
        c.line(chart_x, gy, chart_x + chart_w, gy)
        text(c, str(v), chart_x - 4, gy - 2, size=6.5,
             color=col('grey3'), align='right')

    # X labels
    for d in trajectory:
        wk = d.get('week', 0)
        text(c, f"W{wk}", x_scale(wk), chart_bot - 5,
             size=6.5, color=col('grey3'), align='center')

    # Fill area (polygon under line)
    c.setFillColor(HexColor('#DBEAFE'))
    p_path = c.beginPath()
    p_path.moveTo(x_scale(trajectory[0].get('week', 0)), y_scale(0))
    for d in trajectory:
        p_path.lineTo(x_scale(d.get('week', 0)),
                      y_scale(d.get('expected', 0)))
    p_path.lineTo(x_scale(trajectory[-1].get('week', 0)), y_scale(0))
    p_path.close()
    c.drawPath(p_path, fill=1, stroke=0)

    # Line on top
    c.setStrokeColor(col('blue'))
    c.setLineWidth(2)
    line_path = c.beginPath()
    for i, d in enumerate(trajectory):
        wk = d.get('week', 0)
        val = d.get('expected', 0)
        if i == 0:
            line_path.moveTo(x_scale(wk), y_scale(val))
        else:
            line_path.lineTo(x_scale(wk), y_scale(val))
    c.drawPath(line_path, fill=0, stroke=1)

    # Points + value labels
    for d in trajectory:
        wk = d.get('week', 0)
        val = d.get('expected', 0)
        is_milestone = bool(d.get('milestone'))
        radius = 2.5 if is_milestone else 1.8

        c.setFillColor(white)
        c.circle(x_scale(wk), y_scale(val), radius + 0.8, fill=1, stroke=0)
        c.setFillColor(col('blue'))
        c.circle(x_scale(wk), y_scale(val), radius, fill=1, stroke=0)

        text(c, str(val), x_scale(wk), y_scale(val) + 4,
             'Helvetica-Bold', 7, col('navy2'), align='center')

    y -= chart_h + 2*mm

    # Disclaimer
    disc_h = 8*mm
    fill_rect(c, ML, y - disc_h, CW, disc_h, HexColor('#FFF7ED'),
              radius=2*mm)
    text(c, 'Estimate based on typical recovery for this condition. '
            'Individual recovery varies \u2014 discuss with your physiotherapist.',
         ML + 4*mm, y - disc_h + 3*mm, size=7, color=HexColor('#92400E'))
    y -= disc_h + 4*mm
    return y


def generate_plan_pdf(patient, plan, output_path):
    c = rc.Canvas(output_path, pagesize=A4)
    page_num = [1]

    FOOTER_H = 14 * mm
    sec_h    = 9.5 * mm
    HDR2     = 19 * mm

    name       = patient.get('name', 'Patient')
    age        = patient.get('age', '')
    gender     = patient.get('gender', '')
    zone       = patient.get('zone', '')
    condition  = patient.get('condition', '')
    pain_score = patient.get('pain_score', 5)

    # ── Page helpers ─────────────────────────────────────────────────
    def draw_mini_header():
        gradient(c, 0, H-HDR2, W, HDR2, col('navy1'), col('navy2'))
        mini_logo_w = 28 * mm
        mini_logo_h = mini_logo_w * LOGO_ASPECT
        logo_y = H - HDR2/2 - mini_logo_h/2   # vertically centred in mini-header
        if os.path.exists(LOGO_PATH):
            c.drawImage(LOGO_PATH, ML, logo_y, width=mini_logo_w, height=mini_logo_h, mask='auto')
        text(c, f'Treatment Plan — {name}',
             ML + mini_logo_w + 5*mm, H - HDR2/2 - 3, size=7.5, color=col('grey3'))

    def new_page():
        draw_footer(c, page_num[0])
        c.showPage()
        page_num[0] += 1
        draw_mini_header()
        return H - HDR2 - 5*mm

    def need_page(y, needed):
        if y - needed < FOOTER_H:
            return new_page()
        return y

    # ── PAGE 1: HEADER ───────────────────────────────────────────────
    HDR = 72 * mm
    gradient(c, 0, H-HDR, W, HDR, col('navy1'), col('navy2'))

    # Logo image — top-left, bottom y = H - 32*mm
    logo_w = 50 * mm
    logo_h = logo_w * LOGO_ASPECT
    if os.path.exists(LOGO_PATH):
        c.drawImage(LOGO_PATH, ML, H - 32*mm, width=logo_w, height=logo_h, mask='auto')

    # Treatment Plan badge — top-right
    bw = 50*mm
    bh = 9*mm
    bx = W - MR - bw
    by = H - 23*mm
    fill_rect(c, bx, by, bw, bh, col('blue'), radius=2*mm)
    text(c, 'TREATMENT PLAN', bx + bw / 2, by + bh / 2 - 2.2, 'Helvetica-Bold', 8, white, 'center')

    # BETA badge
    beta_w = 22*mm
    beta_h = 6*mm
    beta_x = W - MR - beta_w
    beta_y = H - 33*mm
    fill_rect(c, beta_x, beta_y, beta_w, beta_h, HexColor('#3B6FE8'), radius=2*mm)
    text(c, 'BETA', beta_x + beta_w / 2, beta_y + beta_h / 2 - 2.2, 'Helvetica-Bold', 7.5, white, 'center')

    # Patient name + date — well below logo bottom (H - 32*mm)
    text(c, patient.get('date', ''), W-MR, H-50*mm, size=7.5, color=col('grey3'), align='right')
    text(c, name, ML, H-50*mm, 'Helvetica-Bold', 22, white)

    # Demographics
    text(c, f"{age}{'y  ·  ' if age else ''}{gender}{'  ·  ' if gender else ''}{zone}",
         ML, H-58*mm, size=9.5, color=col('grey3'))

    # Condition tag
    c.setFont('Helvetica-Bold', 7.5)
    tw = c.stringWidth(condition, 'Helvetica-Bold', 7.5) + 10
    fill_rect(c, ML, H-69.5*mm, tw, 6.5*mm, col('navy2'), radius=2*mm)
    text(c, condition, ML+5, H-65*mm, 'Helvetica-Bold', 7.5, col('blue_l'))

    # ── STAT PILLS ───────────────────────────────────────────────────
    stats_y = H - HDR - 2*mm
    pill_h  = 18 * mm
    pw      = (CW - 7.5*mm) / 3
    pain_color = col('red') if pain_score >= 7 else (col('amber') if pain_score >= 4 else col('green'))
    pkg_label  = plan.get('package', 'Orthopaedic')
    stat_data  = [
        ('PAIN SCORE', f'{pain_score}/10',                col('grey_l'), pain_color),
        ('DURATION',   f"{plan.get('duration_weeks', 8)}w", col('blue_l'), col('blue')),
        ('PACKAGE',    pkg_label[:18],                      col('blue_l'), col('blue')),
    ]
    for i, (lbl, val, bg, vc) in enumerate(stat_data):
        px = ML + i * (pw + 2.5*mm)
        fill_rect(c, px, stats_y-pill_h, pw, pill_h, bg, radius=2.5*mm)
        text(c, lbl, px+4*mm, stats_y-5.5*mm, size=6.5, color=col('grey2'))
        val_size = 11 if len(val) > 12 else 14
        text(c, val, px+4*mm, stats_y-13*mm, 'Helvetica-Bold', val_size, vc)

    y = stats_y - pill_h - 4*mm

    # ── CLINICAL IMPRESSION ──────────────────────────────────────────
    fill_rect(c, ML, y-sec_h, CW, sec_h, col('navy2'), radius=2.5*mm)
    text(c, '◈  CLINICAL IMPRESSION', ML+4*mm, y-sec_h+3.2*mm, 'Helvetica-Bold', 8.5, white)
    y -= sec_h + 2*mm

    impression = plan.get('clinical_impression', '')
    imp_words  = impression.split()
    imp_line_w = CW - 10*mm
    imp_lines  = []; lbuf = []
    for wd in imp_words:
        test_ln = ' '.join(lbuf + [wd])
        if c.stringWidth(test_ln, 'Helvetica', 8.5) <= imp_line_w:
            lbuf.append(wd)
        else:
            if lbuf: imp_lines.append(' '.join(lbuf))
            lbuf = [wd]
    if lbuf: imp_lines.append(' '.join(lbuf))
    imp_h = max(18*mm, len(imp_lines) * 11 + 8*mm)
    fill_rect(c, ML, y-imp_h, CW, imp_h, col('blue_l'), radius=2*mm)
    fill_rect(c, ML, y-imp_h, 2.5*mm, imp_h, col('blue'), radius=1.5*mm)
    c.setFont('Helvetica', 8.5); c.setFillColor(col('grey1'))
    ly_imp = y - 5*mm
    for imp_line in imp_lines:
        c.drawString(ML+6*mm, ly_imp, imp_line); ly_imp -= 11
    y -= imp_h + 4*mm

    # ── GOALS & VISIT PLAN ───────────────────────────────────────────
    fill_rect(c, ML, y-sec_h, CW, sec_h, col('blue'), radius=2.5*mm)
    text(c, '◎  GOALS & VISIT PLAN', ML+4*mm, y-sec_h+3.2*mm, 'Helvetica-Bold', 8.5, white)
    y -= sec_h + 3*mm

    short_goals = plan.get('short_term_goals', [])
    long_goals  = plan.get('long_term_goals', [])
    col_l       = CW * 0.5
    goal_top    = y
    max_drop    = 0
    for gi, (goals, lbl) in enumerate([(short_goals, 'Short-term'), (long_goals, 'Long-term')]):
        gx = ML + gi * col_l
        text(c, lbl, gx+2, goal_top-4, 'Helvetica-Bold', 7.5, col('grey2'))
        gy = goal_top - 4 - 12
        drop = 0
        for g in goals[:4]:
            used = wrap_text(c, '→ '+g, gx+2, gy, col_l-8*mm,
                             size=7.5, color=col('grey1'), leading=10, max_lines=4)
            gy -= used + 5
            drop += used + 5
        max_drop = max(max_drop, drop)
    y = goal_top - 16 - max_drop - 4

    # Visit frequency
    vf_h = 8 * mm
    fill_rect(c, ML, y-vf_h, CW, vf_h, col('blue_l'), radius=2*mm)
    c.setFont('Helvetica-Bold', 7.5); c.setFillColor(col('blue'))
    c.drawString(ML+4*mm, y-vf_h+2.5*mm, 'Visit plan:')
    c.setFont('Helvetica', 7.5); c.setFillColor(col('grey1'))
    c.drawString(ML+22*mm, y-vf_h+2.5*mm, plan.get('visit_frequency', ''))
    y -= vf_h + 4*mm

    # ── METRICS TABLE ────────────────────────────────────────────────
    fill_rect(c, ML, y-sec_h, CW, sec_h, col('navy1'), radius=2.5*mm)
    text(c, '◉  KEY MEASUREMENTS', ML+4*mm, y-sec_h+3.2*mm, 'Helvetica-Bold', 8.5, white)
    y -= sec_h + 2*mm

    col_widths = [CW*0.38, CW*0.25, CW*0.25, CW*0.12]
    fill_rect(c, ML, y-8*mm, CW, 8*mm, col('navy1'))
    for ci, (lbl, cw2) in enumerate(zip(['Metric', 'Baseline', 'Target', 'Frequency'], col_widths)):
        cx = ML + sum(col_widths[:ci])
        text(c, lbl, cx+3, y-5.5*mm, 'Helvetica-Bold', 6.5, white)
    y -= 8*mm

    row_h = 12 * mm
    for mi, m in enumerate(plan.get('metrics', [])[:5]):
        row_bg = col('grey_l') if mi % 2 == 0 else white
        fill_rect(c, ML, y-row_h, CW, row_h, row_bg)
        vals   = [m.get('name',''), m.get('baseline',''), m.get('target',''), m.get('frequency','')]
        colors = [col('grey1'), col('amber'), col('green'), col('grey2')]
        fonts  = ['Helvetica-Bold', 'Helvetica-Bold', 'Helvetica-Bold', 'Helvetica']
        for ci, (val, cw2, cc, fn) in enumerate(zip(vals, col_widths, colors, fonts)):
            cx = ML + sum(col_widths[:ci])
            wrap_text(c, val, cx+3, y-4*mm, cw2-4, font=fn, size=7, color=cc, leading=9, max_lines=2)
        y -= row_h

    draw_footer(c, page_num[0])
    c.showPage()
    page_num[0] += 1

    # ── TREATMENT PHASES ─────────────────────────────────────────────
    draw_mini_header()
    y = H - HDR2 - 3*mm

    fill_rect(c, ML, y-sec_h, CW, sec_h, col('blue'), radius=2.5*mm)
    text(c, '▸  TREATMENT PHASES', ML+4*mm, y-sec_h+3.2*mm, 'Helvetica-Bold', 8.5, white)
    y -= sec_h + 3*mm

    foot_h = 16 * mm
    for i, phase in enumerate(plan.get('phases', [])[:3]):
        pc        = PHASE_COLS[i]  if i < len(PHASE_COLS)  else PHASE_COLS[-1]
        pl        = PHASE_LIGHT[i] if i < len(PHASE_LIGHT) else PHASE_LIGHT[-1]
        exercises = phase.get('exercises', [])[:5]
        card_h    = 11*mm + 7*mm + len(exercises)*12*mm + foot_h

        y = need_page(y, card_h + 3.5*mm)

        # Phase header
        fill_rect(c, ML, y-11*mm, CW, 11*mm, pc, radius=2*mm)
        text(c, f"Phase {phase.get('number', i+1)}  —  {phase.get('name', '')}",
             ML+4*mm, y-7*mm, 'Helvetica-Bold', 9.5, white)
        text(c, phase.get('week_range', ''), W-MR-4, y-7*mm,
             size=7.5, color=HexColor('#C0D8FF'), align='right')

        # Goals row
        fill_rect(c, ML+2.5*mm, y-11*mm-7*mm, CW-2.5*mm, 7*mm, pl)
        text(c, 'Goals:', ML+5.5*mm, y-11*mm-4.5*mm, 'Helvetica-Bold', 6.5, pc)
        goals_str = '  ·  '.join(phase.get('goals', [])[:3])
        wrap_text(c, goals_str, ML+18*mm, y-11*mm-4*mm, CW-20*mm,
                  size=6.5, color=col('grey1'), leading=8, max_lines=2)

        # Exercises
        ey = y - 11*mm - 7*mm
        for ei, ex in enumerate(exercises):
            row_bg = white if ei % 2 == 0 else col('grey_l')
            fill_rect(c, ML+2.5*mm, ey-12*mm, CW-2.5*mm, 12*mm, row_bg)
            fill_rect(c, ML+5.5*mm, ey-5.5*mm, 3, 3, pc, radius=1.5)
            text(c, ex.get('name', ''), ML+9.5*mm, ey-4.5*mm, 'Helvetica-Bold', 8, col('grey1'))
            wrap_text(c, ex.get('prescription', ''), ML+9.5*mm, ey-9*mm, CW-12*mm,
                      size=7, color=col('grey2'), leading=8, max_lines=2)
            c.setStrokeColor(col('line')); c.setLineWidth(0.3)
            c.line(ML+2.5*mm, ey-12*mm, ML+CW, ey-12*mm)
            ey -= 12*mm

        # Phase footer: modalities + precautions
        fill_rect(c, ML+2.5*mm, ey-foot_h, CW-2.5*mm, foot_h, col('grey_l'))
        text(c, 'Modalities:', ML+5.5*mm, ey-4.5*mm, 'Helvetica-Bold', 6.5, col('grey2'))
        wrap_text(c, phase.get('modalities', ''), ML+24*mm, ey-4*mm, CW-27*mm,
                  size=6.5, color=col('grey2'), leading=8, max_lines=2)
        wrap_text(c, '⚠  ' + phase.get('precautions', ''), ML+5.5*mm, ey-foot_h+5*mm,
                  CW-8*mm, size=6.5, color=col('amber'), leading=8, max_lines=2)

        # Left accent bar
        c.setStrokeColor(pc); c.setLineWidth(2)
        c.line(ML, y-card_h, ML, y)
        y -= card_h + 3.5*mm

    # ── RED FLAGS + HOME ADVICE ──────────────────────────────────────
    item_h = 14 * mm
    hdr_h  = 7.5 * mm
    flags  = plan.get('red_flags', [])
    advice = plan.get('home_advice', [])
    n_items = max(len(flags[:5]), len(advice[:5]))
    box_h  = hdr_h + n_items * item_h + 2*mm

    y = need_page(y, box_h + sec_h + 14*mm)

    fill_rect(c, ML, y-sec_h, CW, sec_h, col('navy1'), radius=2.5*mm)
    text(c, '◎  HOME PROGRAMME', ML+4*mm, y-sec_h+3.2*mm, 'Helvetica-Bold', 8.5, white)
    y -= sec_h + 4*mm

    half = (CW - 5*mm) / 2

    def list_box(cx, cy, w2, title, items, hc_color, bg_color, icon, text_color):
        _item_h = 14*mm; _hdr_h = 7.5*mm
        _total  = _hdr_h + len(items[:5]) * _item_h + 2*mm
        fill_rect(c, cx, cy-_total, w2, _total, bg_color, radius=2*mm)
        fill_rect(c, cx, cy-_hdr_h, w2, _hdr_h, hc_color, radius=2*mm)
        fill_rect(c, cx, cy-_hdr_h, w2, _hdr_h/2, hc_color)
        text(c, title, cx+4*mm, cy-_hdr_h+2.5*mm, 'Helvetica-Bold', 7.5, white)
        iy = cy - _hdr_h - 2*mm
        for item in items[:5]:
            wrap_text(c, icon+'  '+item, cx+3*mm, iy-2.5*mm, w2-6*mm,
                      size=7, color=text_color, leading=9, max_lines=3)
            iy -= _item_h
        return _total

    fh1 = list_box(ML,            y, half, '⚑  RED FLAGS',  flags,  col('red'),  col('red_l'),  '▸', col('red'))
    list_box(ML+half+5*mm, y, half, '✓  HOME ADVICE', advice, col('blue'), col('blue_l'), '✓', col('navy2'))
    y -= fh1 + 4*mm

    # ── PAIN RECOVERY TRAJECTORY ─────────────────────────────────────
    trajectory = plan.get('pain_trajectory', [])
    if trajectory:
        if y < 90*mm:
            y = new_page()
        y = draw_pain_trajectory(c, y, trajectory)

    # ── FOLLOW-UP & CONTINUITY ───────────────────────────────────────
    fu             = plan.get('followup', {})
    reassessment   = fu.get('reassessment_date', '—')
    maintenance    = fu.get('maintenance_frequency', '—')
    criteria       = fu.get('contact_criteria', [])
    escalation_txt = fu.get('escalation_pathway',
                            'Attending physio → Lifetime Health clinical team')

    fu_est = sec_h + 4*mm + 14*mm + 4*mm + 14 + len(criteria)*8*mm + 4*mm + 10*mm + 6*mm
    y = need_page(y, fu_est + 10*mm)

    fill_rect(c, ML, y-sec_h, CW, sec_h, col('blue'), radius=2.5*mm)
    text(c, '◷  FOLLOW-UP & CONTINUITY', ML+4*mm, y-sec_h+3.2*mm, 'Helvetica-Bold', 8.5, white)
    y -= sec_h + 4*mm

    # Two stat cards: reassessment + maintenance
    card_w2 = (CW - 5*mm) / 2
    card_h2 = 14 * mm
    for ci2, (lbl2, val2) in enumerate([('Next reassessment', reassessment),
                                         ('Maintenance visits', maintenance)]):
        cx2 = ML + ci2 * (card_w2 + 5*mm)
        fill_rect(c, cx2, y-card_h2, card_w2, card_h2, col('blue_l'), radius=2*mm)
        text(c, lbl2, cx2+4*mm, y-5*mm, 'Helvetica-Bold', 6.5, col('grey2'))
        wrap_text(c, val2, cx2+4*mm, y-9*mm, card_w2-8*mm,
                  'Helvetica-Bold', 8, col('navy2'), leading=10, max_lines=2)
    y -= card_h2 + 4*mm

    # Contact criteria
    text(c, 'Call your therapist if:', ML, y-4, 'Helvetica-Bold', 8, col('navy2'))
    y -= 14
    for crit in criteria:
        fill_rect(c, ML, y-8*mm, CW, 8*mm, col('blue_pale'))
        c.setStrokeColor(col('line')); c.setLineWidth(0.3)
        c.line(ML, y-8*mm, ML+CW, y-8*mm)
        text(c, '·  ' + crit, ML+4*mm, y-5.5*mm, size=7.5, color=col('grey1'))
        y -= 8*mm
    y -= 4*mm

    # Escalation pathway
    esc_h = 10 * mm
    fill_rect(c, ML, y-esc_h, CW, esc_h, col('blue_l'), radius=2*mm)
    text(c, 'Escalation pathway:', ML+4*mm, y-4*mm, 'Helvetica-Bold', 7, col('navy2'))
    text(c, escalation_txt, ML+47*mm, y-4*mm, size=7.5, color=col('blue'))
    y -= esc_h + 6*mm

    # ── RECOMMENDED PACKAGE ──────────────────────────────────────────
    pkg_name = plan.get('package', 'Orthopaedic Physiotherapy Plan')

    pkg_h = sec_h + 4*mm + 18*mm + 4*mm
    y = need_page(y, pkg_h + 10*mm)

    fill_rect(c, ML, y-sec_h, CW, sec_h, col('navy2'), radius=2.5*mm)
    text(c, '◉  RECOMMENDED PACKAGE', ML+4*mm, y-sec_h+3.2*mm, 'Helvetica-Bold', 8.5, white)
    y -= sec_h + 4*mm

    fill_rect(c, ML, y-18*mm, CW, 18*mm, col('blue_l'), radius=2*mm)
    fill_rect(c, ML, y-18*mm, 3*mm, 18*mm, col('blue'), radius=1.5*mm)
    text(c, pkg_name, ML+7*mm, y-7*mm, 'Helvetica-Bold', 12, col('navy2'))
    text(c, 'Based on diagnosis, chronicity, and patient profile',
         ML+7*mm, y-14*mm, size=7.5, color=col('grey2'))
    y -= 18*mm + 4*mm  # noqa: F841

    draw_footer(c, page_num[0])
    c.save()
    print(f'PDF saved: {output_path}')


# ── SAMPLE DATA (for testing) ────────────────────────────────────────
SAMPLE_PATIENT = {
    'name': 'Meena Sharma',
    'age': '58',
    'gender': 'Female',
    'zone': 'Jayanagar',
    'condition': 'Total Knee Replacement (Left)',
    'pain_score': 6,
    'date': '29 April 2026'
}

SAMPLE_PLAN = {
    'clinical_impression': 'Post-TKR patient at Day 12 with moderate pain (6/10), knee flexion limited to 65°, and partial weight-bearing on a walker. Diabetes mellitus elevates infection and healing risk. Priority: swelling control before progressive loading.',
    'short_term_goals': ['Reduce pain to ≤3/10 within 2 weeks', 'Achieve 90° knee flexion', 'Safe independent transfers'],
    'long_term_goals': ['Independent walking without aid by Week 10', 'Return to full household activities'],
    'duration_weeks': 10,
    'visit_frequency': '5x/week (Wk 1–2), 3x/week (Wk 3–6), 2x/week (Wk 7+)',
    'phases': [
        {
            'number': 1, 'name': 'Pain Control & Protection', 'week_range': 'Week 1–2',
            'goals': ['Reduce swelling', 'Initiate gentle ROM', 'Safe transfers'],
            'exercises': [
                {'name': 'Ankle pumps', 'prescription': '20 reps every 2 hrs — DVT prevention'},
                {'name': 'Quad sets (isometric)', 'prescription': '10 reps × 3 sets, 2x daily'},
                {'name': 'Heel slides', 'prescription': '10 reps × 2 sets, 2x daily'},
                {'name': 'Straight leg raises', 'prescription': '10 reps × 3 sets'},
                {'name': 'Assisted knee flexion', 'prescription': '5 reps × 2 sets, to comfort only — do not push through pain'},
            ],
            'modalities': 'Ice 15 min post-session — no TENS/US Week 1',
            'precautions': 'No forced flexion. Full weight-bearing only with walker.'
        },
        {
            'number': 2, 'name': 'Mobility & Strengthening', 'week_range': 'Week 3–6',
            'goals': ['Achieve 110° flexion', 'Independent transfers', 'Stairs with rail'],
            'exercises': [
                {'name': 'Short arc quads', 'prescription': '15 reps × 3 sets'},
                {'name': 'Mini squats (0–45°)', 'prescription': '10 reps × 3 sets'},
                {'name': 'Step-ups (low step)', 'prescription': '10 reps × 2 sets each leg'},
                {'name': 'Standing hip abduction', 'prescription': '15 reps × 3 sets'},
                {'name': 'Gait training', 'prescription': 'Walker → walking stick progression, supervised'},
            ],
            'modalities': 'TENS 20 min if pain ≥4/10',
            'precautions': 'No knee valgus in squats. Avoid deep flexion >90° until Wk 5.'
        },
        {
            'number': 3, 'name': 'Function & Return to Activity', 'week_range': 'Week 7–10',
            'goals': ['Walk 500m independently', 'Full household ADLs', 'Floor-to-stand'],
            'exercises': [
                {'name': 'Leg press (bodyweight)', 'prescription': '15 reps × 3 sets'},
                {'name': 'Single-leg balance', 'prescription': '30 sec × 3 each side'},
                {'name': 'Full stair training', 'prescription': 'Up/down without rail'},
                {'name': 'Car transfer practice', 'prescription': 'ADL training'},
                {'name': 'Outdoor walking', 'prescription': '10 min → 30 min progressive'},
            ],
            'modalities': 'Modalities only as needed for symptom management',
            'precautions': 'Stop if pain >4/10. Report any pop or click immediately.'
        }
    ],
    'metrics': [
        {'name': 'Pain Score (NRS)', 'baseline': '6/10', 'target': '≤2/10', 'frequency': 'Every session'},
        {'name': 'Knee Flexion ROM', 'baseline': '65°', 'target': '≥120°', 'frequency': 'Every 7 visits'},
        {'name': 'KOOS-12 Score', 'baseline': '28/100', 'target': '≥65/100', 'frequency': 'Every 7 visits'},
        {'name': 'Blood Glucose', 'baseline': 'Check at first visit', 'target': '80–180 mg/dL', 'frequency': 'Every session (diabetic)'},
    ],
    'red_flags': [
        'Sudden severe pain or audible pop in knee',
        'Spreading redness, heat or swelling beyond the joint',
        'Fever >38.5°C — infection risk elevated in diabetic patient',
        'Blood glucose <70 or >300 mg/dL at any visit',
        'Numbness, tingling or colour change in foot',
    ],
    'home_advice': [
        'Ice knee 15 min after every exercise session',
        'Keep leg elevated when resting to reduce swelling',
        'Daily blood sugar monitoring — share readings with care team',
        'High protein diet (eggs, dal, paneer) — accelerates healing',
        'Do not skip Week 1–2 sessions — continuity is critical for recovery',
    ],
    'pain_trajectory': [
        {'week': 0,  'expected': 6, 'milestone': 'Baseline'},
        {'week': 2,  'expected': 4, 'milestone': 'End of Phase 1'},
        {'week': 4,  'expected': 3},
        {'week': 6,  'expected': 2, 'milestone': 'End of Phase 2'},
        {'week': 8,  'expected': 2},
        {'week': 10, 'expected': 2, 'milestone': 'Discharge target'},
    ],
    'package': 'Senior Citizen Physiotherapy Plan',
    'followup': {
        'reassessment_date': 'Week 8 — 24 Jun 2026',
        'maintenance_frequency': '1x per month for 3 months after discharge',
        'contact_criteria': [
            'Sudden increase in pain or swelling around the knee',
            'Blood glucose above 300 mg/dL at any point',
            'Signs of wound infection: redness, discharge, warmth',
            'Unable to bear weight after Week 3 of programme'
        ],
        'escalation_pathway': 'Attending physio → Lifetime Health clinical team'
    }
}


if __name__ == '__main__':
    if '--json' in sys.argv:
        idx = sys.argv.index('--json')
        data = json.loads(sys.argv[idx+1])
        generate_plan_pdf(data['patient'], data['plan'], data.get('output', 'plan.pdf'))
    elif '--help' in sys.argv:
        print(__doc__)
    else:
        output = os.path.join(os.path.dirname(__file__), 'sample_plan.pdf')
        generate_plan_pdf(SAMPLE_PATIENT, SAMPLE_PLAN, output)
