"""
Lifetime Health — Caregiver Care Plan PDF Generator
Requires: pip install reportlab

Usage:
  python3 generate_caregiver_pdf.py            # generates the sample bedbound plan
  python3 generate_caregiver_pdf.py --help     # shows usage

In production this will be called by the Node.js server:
  python3 generate_caregiver_pdf.py --json '{"patient":...,"plan":...}'

TONE. This document is read by the patient and their family, and it is printed
and kept in the patient's home so a replacement nurse reads the same sheet.
It is written FOR the patient: address them directly, say "your nurse", never
"caregiver" or "staff", and keep the language plain.

DUPLICATION. The brand colours, gradient(), fill_rect(), text(), wrap_text(),
draw_footer(), the logo constants and the page/margin constants are copied
verbatim from generate_pdf.py rather than imported. That generator is live and
is deliberately not being refactored, so the two files must be kept in step by
hand if the brand changes. Three helpers named in the spec do not exist under
those names in the physio file: txt() is text(), and section_header() and
draw_slim_header() are inlined there (as the fill_rect+text pattern and as the
nested draw_mini_header()). They are factored out here.
"""
from reportlab.pdfgen import canvas as rc
from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import HexColor, white
from reportlab.lib.units import mm
import json, sys, os, re

# ── Copied verbatim from generate_pdf.py ─────────────────────────────────
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

# Billing pill colours, per spec
BILL_GREEN_BG = HexColor('#DCFCE7')
BILL_GREEN_FG = HexColor('#166534')
BILL_AMBER_BG = HexColor('#FEF3C7')
BILL_AMBER_FG = HexColor('#92400E')


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

# Logo asset — 1557 × 611 px, aspect ratio ≈ 2.55 : 1
LOGO_PATH   = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assets', 'logo.png')
LOGO_ASPECT = 611 / 1557   # height / width


def draw_footer(c, page_num):
    """As generate_pdf.py, minus its 'for clinical use only' clause — this
    document is handed to the patient, so that line would be untrue."""
    fill_rect(c, 0, 0, W, 11*mm, col('grey_l'))
    c.setStrokeColor(col('line')); c.setLineWidth(0.5); c.line(0, 11*mm, W, 11*mm)
    text(c, 'Lifetime Health  ·  lifetimehealth.in', ML, 4*mm, size=6.5, color=col('grey3'))
    text(c, f'Page {page_num}', W-MR, 4*mm, size=6.5, color=col('grey3'), align='right')


# ── Layout helpers ───────────────────────────────────────────────────────
SEC_H    = 9.5 * mm
HDR2     = 19 * mm
FOOTER_H = 14 * mm
# A section heading plus the gap under it. Callers add their own first item, so a
# section moves to the next page only when its heading and first item cannot fit.
SECTION_LEAD = SEC_H + 3 * mm

def measure(c, s, max_width, font='Helvetica', size=8):
    """Wrap s to max_width and return every line. Never truncates — callers
    size their boxes from len() of the result."""
    lines, buf = [], []
    for word in str(s).split():
        test_ln = ' '.join(buf + [word])
        if c.stringWidth(test_ln, font, size) <= max_width or not buf:
            buf.append(word)
        else:
            lines.append(' '.join(buf))
            buf = [word]
    if buf:
        lines.append(' '.join(buf))
    return lines or ['']

def draw_lines(c, lines, x, y, font='Helvetica', size=8, color=None, leading=11):
    """Draw pre-measured lines from measure(). Returns height used."""
    if color: c.setFillColor(color)
    c.setFont(font, size)
    for i, ln in enumerate(lines):
        c.drawString(x, y - i * leading, ln)
    return len(lines) * leading

def section_header(c, y, label, bg=None, icon='◈'):
    """The section bar used throughout both documents. Returns the new y."""
    bg = bg or col('navy2')
    fill_rect(c, ML, y - SEC_H, CW, SEC_H, bg, radius=2.5*mm)
    text(c, f'{icon}  {label}', ML + 4*mm, y - SEC_H + 3.2*mm, 'Helvetica-Bold', 8.5, white)
    return y - SEC_H - 3*mm

def draw_slim_header(c, name):
    """Compact header repeated on continuation pages. Returns the new y."""
    gradient(c, 0, H-HDR2, W, HDR2, col('navy1'), col('navy2'))
    lw = 28 * mm
    lh = lw * LOGO_ASPECT
    if os.path.exists(LOGO_PATH):
        c.drawImage(LOGO_PATH, ML, H - HDR2/2 - lh/2, width=lw, height=lh, mask='auto')
    text(c, f'Care Plan — {name}', ML + lw + 5*mm, H - HDR2/2 - 3, size=7.5, color=col('grey3'))
    return H - HDR2 - 5*mm

def pill(c, x, y, label, bg, fg, size=6.5, pad=4):
    """Small rounded tag sized to its text. Returns its width."""
    c.setFont('Helvetica-Bold', size)
    w = c.stringWidth(label, 'Helvetica-Bold', size) + pad * 2
    h = 5 * mm
    fill_rect(c, x, y, w, h, bg, radius=1.8*mm)
    text(c, label, x + w/2, y + h/2 - 2, 'Helvetica-Bold', size, fg, 'center')
    return w

# Short labels for the record-sheet columns, keyed by the monitoring measure
MEASURE_ABBR = {
    'blood pressure': 'BP',
    'pulse':          'Pulse',
    'oxygen (spo2)':  'SpO2',
    'oxygen':         'SpO2',
    'spo2':           'SpO2',
    'temperature':    'Temp',
    'blood sugar':    'Sugar',
}

def measure_abbr(name):
    key = str(name).strip().lower()
    if key in MEASURE_ABBR:
        return MEASURE_ABBR[key]
    for k, v in MEASURE_ABBR.items():
        if k in key:
            return v
    return str(name)[:5]

CARE_TYPE_SHORT = {
    'post-surgical recovery':          'Post-surgical',
    'elderly dependency care':         'Elderly care',
    'bedbound / high-dependency care': 'Bedbound care',
    'chronic condition support':       'Chronic care',
    'stroke and neurological care':    'Stroke / neuro',
    'palliative and comfort care':     'Palliative',
}

def care_type_short(care_type):
    return CARE_TYPE_SHORT.get(str(care_type).strip().lower(), str(care_type)[:18])

def service_short(tier):
    """'Advanced — 8 hours' -> '8 hours daily'. Falls back to the raw tier."""
    t = str(tier)
    for dash in ('—', '–', '-'):
        if dash in t:
            tail = t.split(dash)[-1].strip()
            if tail:
                return f'{tail} daily'
            break
    return t[:18]

NO_EXERCISE = 'No exercise — rest advised'
# A short flexible lunch break and a long overnight rest are different things to
# the family reading the plan, so they are named and tagged differently
REST_BLOCK  = 'Nurse rest period'
BREAK_BLOCK = 'Nurse lunch break'

def is_rest_block(name):
    return name in (REST_BLOCK, BREAK_BLOCK)

def med_sort_key(rows):
    """Order by clock time where a row parses as one; anything else ('after
    breakfast') keeps its entered order, after the timed rows."""
    def parse(t):
        m = re.match(r'^\s*(\d{1,2})[:.](\d{2})\s*(am|pm)?\s*$', str(t or ''), re.I)
        if not m:
            m2 = re.match(r'^\s*(\d{1,2})\s*(am|pm)\s*$', str(t or ''), re.I)
            if not m2:
                return None
            hh, mm_, ap = int(m2.group(1)), 0, m2.group(2)
        else:
            hh, mm_, ap = int(m.group(1)), int(m.group(2)), m.group(3)
        if ap:
            ap = ap.lower()
            if ap == 'pm' and hh != 12: hh += 12
            if ap == 'am' and hh == 12: hh = 0
        if not (0 <= hh <= 23 and 0 <= mm_ <= 59):
            return None
        return hh * 60 + mm_
    timed, untimed = [], []
    for i, r in enumerate(rows):
        v = parse(r.get('time'))
        (timed if v is not None else untimed).append((v if v is not None else 0, i, r))
    timed.sort(key=lambda x: (x[0], x[1]))
    return [r for _, _, r in timed] + [r for _, _, r in untimed]


def generate_caregiver_pdf(patient, plan, output_path):
    c = rc.Canvas(output_path, pagesize=A4)
    page_num = [1]

    name        = patient.get('name', 'Patient')
    age         = patient.get('age', '')
    gender      = patient.get('gender', '')
    zone        = patient.get('zone', '')
    care_type   = patient.get('care_type', '')
    tier        = plan.get('service_tier') or patient.get('service_tier', '')
    assessed_by = patient.get('assessed_by', '')
    em_name     = str(patient.get('emergency_name', '') or '').strip()
    em_phone    = str(patient.get('emergency_phone', '') or '').strip()
    dr_name     = str(patient.get('doctor_name', '') or '').strip()
    dr_phone    = str(patient.get('doctor_phone', '') or '').strip()

    def new_page():
        draw_footer(c, page_num[0])
        c.showPage()
        page_num[0] += 1
        return draw_slim_header(c, name)

    def need(y, needed):
        """Start a new page if `needed` mm of content will not fit."""
        if y - needed < FOOTER_H:
            return new_page()
        return y

    # ══ PAGE 1 — HEADER ══════════════════════════════════════════════════
    HDR = 72 * mm
    gradient(c, 0, H-HDR, W, HDR, col('navy1'), col('navy2'))

    logo_w = 50 * mm
    logo_h = logo_w * LOGO_ASPECT
    if os.path.exists(LOGO_PATH):
        c.drawImage(LOGO_PATH, ML, H - 32*mm, width=logo_w, height=logo_h, mask='auto')

    bw, bh = 50*mm, 9*mm
    bx, by = W - MR - bw, H - 23*mm
    fill_rect(c, bx, by, bw, bh, col('blue'), radius=2*mm)
    text(c, 'CARE PLAN', bx + bw/2, by + bh/2 - 2.2, 'Helvetica-Bold', 8, white, 'center')

    beta_w, beta_h = 22*mm, 6*mm
    beta_x, beta_y = W - MR - beta_w, H - 33*mm
    fill_rect(c, beta_x, beta_y, beta_w, beta_h, col('blue'), radius=2*mm)
    text(c, 'BETA', beta_x + beta_w/2, beta_y + beta_h/2 - 2.2, 'Helvetica-Bold', 7.5, white, 'center')

    text(c, patient.get('date', ''), W-MR, H-50*mm, size=7.5, color=col('grey3'), align='right')
    text(c, name, ML, H-50*mm, 'Helvetica-Bold', 22, white)

    text(c, f"{age}{'y  ·  ' if age else ''}{gender}{'  ·  ' if gender else ''}{zone}",
         ML, H-58*mm, size=9.5, color=col('grey3'))

    c.setFont('Helvetica-Bold', 7.5)
    tw = c.stringWidth(care_type, 'Helvetica-Bold', 7.5) + 10
    fill_rect(c, ML, H-69.5*mm, tw, 6.5*mm, col('navy2'), radius=2*mm)
    text(c, care_type, ML+5, H-65*mm, 'Helvetica-Bold', 7.5, col('blue_l'))

    # ── Stat pills ───────────────────────────────────────────────────────
    stats_y = H - HDR - 2*mm
    pill_h  = 18 * mm
    pw      = (CW - 7.5*mm) / 3
    stat_data = [
        ('CARE TYPE',   care_type_short(care_type), col('grey_l'), col('navy2')),
        ('SERVICE',     service_short(tier),        col('blue_l'), col('blue')),
        ('ASSESSED BY', assessed_by[:18],           col('grey_l'), col('navy2')),
    ]
    for i, (lbl, val, bg, vc) in enumerate(stat_data):
        px = ML + i * (pw + 2.5*mm)
        fill_rect(c, px, stats_y-pill_h, pw, pill_h, bg, radius=2.5*mm)
        text(c, lbl, px+4*mm, stats_y-5.5*mm, size=6.5, color=col('grey2'))
        val_size = 9 if len(val) > 15 else (11 if len(val) > 12 else 14)
        text(c, val, px+4*mm, stats_y-13*mm, 'Helvetica-Bold', val_size, vc)

    y = stats_y - pill_h - 4*mm

    # ── Emergency contacts ───────────────────────────────────────────────
    # High on page one because this is what someone reaches for in a crisis.
    # Straight from the assessment — never model output.
    contact_bits = []
    if em_name or em_phone:
        contact_bits.append('Emergency contact: ' + ' · '.join([x for x in (em_name, em_phone) if x]))
    if dr_name or dr_phone:
        contact_bits.append('Doctor: ' + ' · '.join([x for x in (dr_name, dr_phone) if x]))

    if contact_bits:
        bar_h = 9 * mm
        fill_rect(c, ML, y - bar_h, CW, bar_h, col('blue_l'), radius=2*mm)
        text(c, '     '.join(contact_bits), ML + 4*mm, y - bar_h + 3.2*mm,
             'Helvetica-Bold', 8, col('navy2'))
        y -= bar_h + 4*mm

    # ── YOUR CARE ────────────────────────────────────────────────────────
    y = section_header(c, y, 'YOUR CARE', col('navy2'))

    summary_lines = measure(c, plan.get('care_summary', ''), CW - 10*mm, 'Helvetica', 8.5)
    box_h = max(18*mm, len(summary_lines) * 11 + 8*mm)
    fill_rect(c, ML, y-box_h, CW, box_h, col('blue_l'), radius=2*mm)
    fill_rect(c, ML, y-box_h, 3*mm, box_h, col('blue'), radius=1.5*mm)
    draw_lines(c, summary_lines, ML+6*mm, y-5*mm, 'Helvetica', 8.5, col('grey1'), 11)
    y -= box_h + 4*mm

    # ── YOUR DAILY ROUTINE ───────────────────────────────────────────────
    y = section_header(c, y, 'YOUR DAILY ROUTINE', col('blue'), icon='◷')

    TIME_COL = 24 * mm          # time sits in its own fixed column
    note_w   = CW - TIME_COL - 6*mm

    for block in plan.get('daily_routine', []):
        rows = []
        for t in block.get('tasks', []):
            note_lines = measure(c, t.get('note', ''), note_w, 'Helvetica', 7) if t.get('note') else []
            # The time column now carries phrases as well as clock times — a
            # flexible break reads "Around midday" — so it wraps rather than
            # running into the task name beside it
            time_lines = measure(c, t.get('time', ''), TIME_COL - 6*mm, 'Helvetica-Bold', 7.5)
            body_h = 6.2*mm + len(note_lines) * 8.5
            row_h = max(8*mm, body_h, 4.2*mm + len(time_lines) * 8.5)
            rows.append((t, note_lines, time_lines, row_h))
        card_h = 7*mm + sum(r[3] for r in rows)

        y = need(y, card_h + 4*mm)

        # The nurse's rest is a scheduled part of the service, not a gap in care,
        # so it is navy with a tag rather than another blue block
        # Not `name` — that holds the patient's name and is used by every
        # subsequent page header
        block_name = block.get('block', '')
        is_rest = is_rest_block(block_name)
        fill_rect(c, ML, y-7*mm, CW, 7*mm, col('navy2') if is_rest else col('blue'), radius=1.5*mm)
        text(c, block_name, ML+4*mm, y-7*mm+2.3*mm, 'Helvetica-Bold', 8, white)
        if is_rest:
            tag = 'BREAK' if block_name == BREAK_BLOCK else 'REST'
            c.setFont('Helvetica-Bold', 6)
            tag_w = c.stringWidth(tag, 'Helvetica-Bold', 6) + 8
            tag_x = ML + 4*mm + c.stringWidth(block_name, 'Helvetica-Bold', 8) + 4*mm
            fill_rect(c, tag_x, y-7*mm+1.8*mm, tag_w, 3.6*mm, col('blue'), radius=1.5*mm)
            text(c, tag, tag_x + tag_w/2, y-7*mm+2.9*mm, 'Helvetica-Bold', 6, white, 'center')
        text(c, block.get('time_range', ''), W-MR-4*mm, y-7*mm+2.3*mm,
             'Helvetica', 7.5, col('blue_l2'), 'right')
        ry = y - 7*mm

        for i, (t, note_lines, time_lines, row_h) in enumerate(rows):
            fill_rect(c, ML, ry-row_h, CW, row_h, white if i % 2 == 0 else col('grey_l'))
            draw_lines(c, time_lines, ML+4*mm, ry-5*mm, 'Helvetica-Bold', 7.5, col('navy2'), 8.5)
            text(c, t.get('task', ''), ML+TIME_COL, ry-5*mm, 'Helvetica-Bold', 8, col('grey1'))
            if note_lines:
                draw_lines(c, note_lines, ML+TIME_COL, ry-5*mm-8, 'Helvetica', 7, col('grey2'), 8.5)
            ry -= row_h

        c.setStrokeColor(col('line')); c.setLineWidth(0.5)
        c.rect(ML, ry, CW, y - 7*mm - ry)
        y = ry - 4*mm

    # ══ MEDICATION SCHEDULE ══════════════════════════════════════════════
    # Its own page, and only when there are medicines. This is the highest-stakes
    # table in the document, so it is sized to be read at arm's length.
    meds = med_sort_key(plan.get('medications') or [])
    if meds:
        y = new_page()
        y = section_header(c, y, 'MEDICATION SCHEDULE', col('navy2'), icon='◈')
        y -= draw_lines(c, measure(c,
            'Give each medicine at the time shown. Tick the record sheet once given. '
            'Never change a dose without speaking to the doctor.', CW, 'Helvetica', 7.5),
            ML, y, 'Helvetica', 7.5, col('grey2'), 9.5)
        y -= 5*mm

        med_w = [CW*0.22, CW*0.48, CW*0.30]
        def med_head(yy):
            fill_rect(c, ML, yy-7*mm, CW, 7*mm, col('navy2'), radius=1.5*mm)
            hx = ML
            for i, hd in enumerate(['Time', 'Medicine', 'Dosage']):
                text(c, hd, hx+3*mm, yy-7*mm+2.3*mm, 'Helvetica-Bold', 7, white)
                hx += med_w[i]
            return yy - 7*mm

        y = med_head(y)
        for i, m in enumerate(meds):
            name_lines = measure(c, m.get('name', ''), med_w[1]-6*mm, 'Helvetica', 9)
            note_lines = measure(c, m.get('note', ''), med_w[1]-6*mm, 'Helvetica-Oblique', 7) if m.get('note') else []
            row_h = max(11*mm, 5*mm + len(name_lines)*10 + len(note_lines)*8.5 + 3*mm)
            if y - row_h < FOOTER_H:
                close_med = y
                c.setStrokeColor(col('line')); c.setLineWidth(0.5)
                c.line(ML, close_med, W-MR, close_med)
                y = new_page()
                y = med_head(y)
            fill_rect(c, ML, y-row_h, CW, row_h, white if i % 2 == 0 else col('grey_l'))
            text(c, m.get('time', ''), ML+3*mm, y-6.5*mm, 'Helvetica-Bold', 9.5, col('navy2'))
            ny = draw_lines(c, name_lines, ML+med_w[0]+3*mm, y-6.5*mm, 'Helvetica', 9, col('grey1'), 10)
            if note_lines:
                draw_lines(c, note_lines, ML+med_w[0]+3*mm, y-6.5*mm-ny, 'Helvetica-Oblique', 7, col('grey2'), 8.5)
            text(c, m.get('dosage', ''), ML+med_w[0]+med_w[1]+3*mm, y-6.5*mm, 'Helvetica-Bold', 9, col('navy2'))
            y -= row_h
        c.setStrokeColor(col('line')); c.setLineWidth(0.5)
        c.line(ML, y, W-MR, y)
        y -= 5*mm

        warn = ("This schedule was recorded from the patient's prescription at assessment. "
                "If any medicine or dose has changed, tell your nurse before the next visit.")
        warn_lines = measure(c, warn, CW - 16*mm, 'Helvetica', 8)
        box_h = len(warn_lines) * 10 + 8*mm
        y = need(y, box_h + 4*mm)
        fill_rect(c, ML, y-box_h, CW, box_h, HexColor('#FEF3C7'), radius=2*mm)
        fill_rect(c, ML, y-box_h, 3*mm, box_h, col('amber'), radius=1.5*mm)
        text(c, '!', ML+6*mm, y-5.5*mm, 'Helvetica-Bold', 10, col('amber'))
        draw_lines(c, warn_lines, ML+11*mm, y-5.5*mm, 'Helvetica', 8, BILL_AMBER_FG, 10)
        y -= box_h + 4*mm

    # ══ CARE EXPLAINED AND EXERCISE ══════════════════════════════════════
    # Sections flow rather than each starting a forced new page, and a section
    # only moves to the next page when its heading plus its FIRST item genuinely
    # will not fit. Reserving a flat slab instead left a third of a page blank.
    body_w = CW - 8*mm
    explained = plan.get('care_explained', [])

    def explained_lines(item):
        return (measure(c, item.get('why', ''), body_w, 'Helvetica', 7.5),
                measure(c, item.get('how', ''), body_w, 'Helvetica', 7.5))

    def explained_card_h(item):
        why_lines, how_lines = explained_lines(item)
        return 6*mm + 4.5*mm + len(why_lines)*9.5 + 4.5*mm + len(how_lines)*9.5 + 4*mm

    y = need(y, SECTION_LEAD + 6*mm + (explained_card_h(explained[0]) if explained else 0))

    y = section_header(c, y, 'YOUR CARE EXPLAINED', col('navy2'))
    text(c, 'What your nurse does at each visit, and why it matters.',
         ML, y-1*mm, 'Helvetica', 7.5, col('grey2'))
    y -= 6*mm

    for item in explained:
        why_lines, how_lines = explained_lines(item)
        card_h = explained_card_h(item)

        y = need(y, card_h + 3*mm)
        top = y

        text(c, item.get('task', ''), ML+2*mm, y-4.5*mm, 'Helvetica-Bold', 10, col('navy2'))
        y -= 6*mm + 3*mm

        text(c, 'WHY THIS MATTERS', ML+2*mm, y, 'Helvetica-Bold', 6, col('blue'))
        y -= 4.5*mm
        y -= draw_lines(c, why_lines, ML+2*mm, y, 'Helvetica', 7.5, col('grey1'), 9.5)

        y -= 3*mm
        text(c, 'HOW IT IS DONE', ML+2*mm, y, 'Helvetica-Bold', 6, col('grey3'))
        y -= 4.5*mm
        y -= draw_lines(c, how_lines, ML+2*mm, y, 'Helvetica', 7.5, col('grey2'), 9.5)

        y -= 4*mm
        c.setStrokeColor(col('line')); c.setLineWidth(0.5)
        c.line(ML, y, W-MR, y)
        y -= 4*mm

    # ── EXERCISE AND MOVEMENT ────────────────────────────────────────────
    # Tiers with no exercise section send exercise_plan as null, and must render
    # nothing at all here rather than an empty heading
    ex = plan.get('exercise_plan') or {}
    types = ex.get('types', [])
    has_exercise = bool(types or ex.get('instructions') or ex.get('precautions'))

    if has_exercise:
      y = need(y, SECTION_LEAD + 14*mm)   # heading plus the pill row or the rest banner
      y = section_header(c, y, 'EXERCISE AND MOVEMENT', col('blue'), icon='◈')

      if NO_EXERCISE in types:
          msg = ('Rest is advised for now. Your nurse will not carry out exercises '
                 'until the clinical team reviews this.')
          msg_lines = measure(c, msg, CW - 12*mm, 'Helvetica', 8)
          box_h = len(msg_lines) * 10 + 8*mm
          y = need(y, box_h + 4*mm)
          fill_rect(c, ML, y-box_h, CW, box_h, HexColor('#FEF3C7'), radius=2*mm)
          fill_rect(c, ML, y-box_h, 3*mm, box_h, col('amber'), radius=1.5*mm)
          text(c, '!', ML+6*mm, y-5.5*mm, 'Helvetica-Bold', 10, col('amber'))
          draw_lines(c, msg_lines, ML+11*mm, y-5.5*mm, 'Helvetica', 8, BILL_AMBER_FG, 10)
          y -= box_h + 4*mm
      else:
          # Type pills, wrapping across rows
          px, py = ML, y - 5*mm
          row_gap = 7 * mm
          for t in types:
              c.setFont('Helvetica-Bold', 7)
              w = c.stringWidth(t, 'Helvetica-Bold', 7) + 8
              if px + w > W - MR:
                  px = ML
                  py -= row_gap
                  y -= row_gap
              fill_rect(c, px, py-1.5*mm, w, 5.5*mm, col('blue_l'), radius=1.8*mm)
              text(c, t, px + w/2, py + 0.3*mm, 'Helvetica-Bold', 7, col('blue'), 'center')
              px += w + 2*mm
          y -= 10*mm

          freq = ex.get('frequency', '')
          if freq:
              y = need(y, 12*mm)
              fill_rect(c, ML, y-8*mm, CW, 8*mm, col('blue_l'), radius=2*mm)
              text(c, 'How often:', ML+4*mm, y-5.3*mm, 'Helvetica-Bold', 7.5, col('grey2'))
              text(c, freq, ML+24*mm, y-5.3*mm, 'Helvetica-Bold', 8.5, col('blue'))
              y -= 8*mm + 4*mm

          instr = ex.get('instructions', '')
          if instr:
              instr_lines = measure(c, instr, CW - 10*mm, 'Helvetica', 8)
              box_h = len(instr_lines) * 10 + 10*mm
              y = need(y, box_h + 4*mm)
              fill_rect(c, ML, y-box_h, CW, box_h, white)
              c.setStrokeColor(col('line')); c.setLineWidth(0.6)
              c.rect(ML, y-box_h, CW, box_h)
              text(c, 'WHAT YOUR NURSE WILL DO', ML+5*mm, y-5*mm, 'Helvetica-Bold', 6, col('grey3'))
              draw_lines(c, instr_lines, ML+5*mm, y-9.5*mm, 'Helvetica', 8, col('grey1'), 10)
              y -= box_h + 4*mm

          prec = ex.get('precautions', '')
          if prec:
              prec_lines = measure(c, prec, CW - 16*mm, 'Helvetica', 8)
              box_h = len(prec_lines) * 10 + 8*mm
              y = need(y, box_h + 4*mm)
              fill_rect(c, ML, y-box_h, CW, box_h, HexColor('#FEF3C7'), radius=2*mm)
              fill_rect(c, ML, y-box_h, 3*mm, box_h, col('amber'), radius=1.5*mm)
              text(c, '!', ML+6*mm, y-5.5*mm, 'Helvetica-Bold', 10, col('amber'))
              draw_lines(c, prec_lines, ML+11*mm, y-5.5*mm, 'Helvetica', 8, BILL_AMBER_FG, 10)
              y -= box_h + 4*mm

    # ══ MONITORING, SAFETY, CONTACT, SUPPLIES ════════════════════════════
    # ── WHAT WE MONITOR ──────────────────────────────────────────────────
    mon = plan.get('monitoring', [])
    cols_w = [CW*0.34, CW*0.20, CW*0.23, CW*0.23]
    heads  = ['Measure', 'When', 'Normal range', 'Call us if']

    def monitor_head(yy):
        fill_rect(c, ML, yy-7*mm, CW, 7*mm, col('navy2'), radius=1.5*mm)
        hx = ML
        for i, hd in enumerate(heads):
            text(c, hd, hx+3*mm, yy-7*mm+2.3*mm, 'Helvetica-Bold', 7, white)
            hx += cols_w[i]
        return yy - 7*mm

    def close_table(yy):
        c.setStrokeColor(col('line')); c.setLineWidth(0.5)
        c.line(ML, yy, W-MR, yy)

    # Reserve the section bar, the column heads and a first row together, so the
    # heading can never sit alone at the foot of a page
    y = need(y, SEC_H + 3*mm + 7*mm + 12*mm)
    y = section_header(c, y, 'WHAT WE MONITOR', col('navy2'), icon='◉')
    y = monitor_head(y)

    for i, m in enumerate(mon):
        cells = [m.get('measure',''), m.get('when',''),
                 m.get('normal_range',''), m.get('call_if','')]
        # No line cap. 'Call us if' is the column that overflows, and it is the
        # one that tells the family when to phone — cutting it mid-sentence is
        # worse than a taller row.
        wrapped = [measure(c, cells[j], cols_w[j]-6*mm, 'Helvetica', 7) for j in range(4)]
        row_h = max(7*mm, max(len(wc) for wc in wrapped) * 9 + 4*mm)
        if y - row_h < FOOTER_H:
            # Rule off what stays behind, then carry the headings over. Without
            # this the reader gets four bare columns and cannot tell which one
            # is the call-us threshold.
            close_table(y)
            y = new_page()
            y = monitor_head(y)
        fill_rect(c, ML, y-row_h, CW, row_h, white if i % 2 == 0 else col('grey_l'))
        cx = ML
        for j, wc in enumerate(wrapped):
            fnt = 'Helvetica-Bold' if j == 0 else 'Helvetica'
            clr = col('red') if j == 3 else (col('navy2') if j == 0 else col('grey2'))
            draw_lines(c, wc, cx+3*mm, y-4.5*mm, fnt, 7, clr, 9)
            cx += cols_w[j]
        y -= row_h
    close_table(y)
    y -= 5*mm

    # ── STAYING SAFE AT HOME ─────────────────────────────────────────────
    safety = plan.get('safety_at_home', [])
    if safety:
        half = CW / 2
        item_w = half - 12*mm
        pairs = [safety[i:i+2] for i in range(0, len(safety), 2)]

        def safety_row_h(pair):
            return max(len(measure(c, s, item_w, 'Helvetica', 7.5)) for s in pair) * 9.5 + 5*mm

        y = need(y, SECTION_LEAD + safety_row_h(pairs[0]) + 2*mm)
        y = section_header(c, y, 'STAYING SAFE AT HOME', col('blue'), icon='◈')

        for pair in pairs:
            # No line cap — the row grows to the tallest item in the pair
            wrapped = [measure(c, s, item_w, 'Helvetica', 7.5) for s in pair]
            row_h = max(len(wc) for wc in wrapped) * 9.5 + 5*mm
            y = need(y, row_h + 2*mm)
            fill_rect(c, ML, y-row_h, CW, row_h, col('blue_l'), radius=2*mm)
            for j, wc in enumerate(wrapped):
                cx = ML + j * half
                text(c, '✓', cx+4*mm, y-5*mm, 'Helvetica-Bold', 8, col('blue'))
                draw_lines(c, wc, cx+9*mm, y-5*mm, 'Helvetica', 7.5, col('grey1'), 9.5)
            y -= row_h + 2*mm
        y -= 2*mm

    # ── WHEN TO CALL US ──────────────────────────────────────────────────
    contacts = plan.get('contact_criteria', [])
    first_contact_h = (len(measure(c, contacts[0], CW - 14*mm, 'Helvetica', 7.5)) * 9.5 + 3.5*mm) if contacts else 0
    y = need(y, SECTION_LEAD + first_contact_h)
    y = section_header(c, y, 'WHEN TO CALL US', col('navy2'), icon='◈')

    for s in contacts:
        lines = measure(c, s, CW - 14*mm, 'Helvetica', 7.5)
        row_h = len(lines) * 9.5 + 3.5*mm
        y = need(y, row_h)
        fill_rect(c, ML, y-row_h, CW, row_h, col('grey_l'))
        c.setFillColor(col('blue'))
        c.circle(ML+4*mm, y-3.6*mm, 1.1, fill=1, stroke=0)
        draw_lines(c, lines, ML+8*mm, y-4.5*mm, 'Helvetica', 7.5, col('grey1'), 9.5)
        y -= row_h + 1
    y -= 3*mm

    esc = plan.get('escalation_pathway', '')
    if esc:
        y = need(y, 12*mm)
        fill_rect(c, ML, y-8*mm, CW, 8*mm, col('blue_l'), radius=2*mm)
        text(c, 'Escalation:', ML+4*mm, y-5.3*mm, 'Helvetica-Bold', 7.5, col('grey2'))
        text(c, esc, ML+24*mm, y-5.3*mm, 'Helvetica-Bold', 8, col('navy2'))
        y -= 8*mm + 3*mm

    y = need(y, 14*mm)
    fill_rect(c, ML, y-10*mm, CW, 10*mm, col('navy2'), radius=2*mm)
    text(c, 'Free expert consultation available at', ML+5*mm, y-6.3*mm, 'Helvetica', 8, white)
    lbl_w = c.stringWidth('Free expert consultation available at ', 'Helvetica', 8)
    text(c, 'lth.doctor/consultation', ML+5*mm+lbl_w, y-6.3*mm, 'Helvetica-Bold', 8, col('blue_l2'))
    y -= 10*mm + 5*mm

    # ── SUPPLIES FOR YOUR CARE ───────────────────────────────────────────
    supplies = plan.get('supplies') or {}
    kits = supplies.get('kits', [])
    consumables = supplies.get('consumables', [])

    if kits or consumables:
        # heading, the two-line allowance note, and the first kit row
        first_kit_h = (6*mm + len(measure(c, kits[0].get('purpose',''), CW - 40*mm, 'Helvetica', 7)) * 8.5 + 3*mm) if kits else 0
        y = need(y, SECTION_LEAD + 13*mm + first_kit_h)
        y = section_header(c, y, 'SUPPLIES FOR YOUR CARE', col('blue'), icon='◈')

        # The allowance is a total per session, not one of each type. The old
        # wording described the per-type rule the pills no longer follow, which
        # is the kind of thing a family disputes a bill against.
        allowance = supplies.get('kit_allowance', 2)
        intro = (f'Your package includes {allowance} kits per session. The disposable kit is '
                 'always one of them. Additional kits are charged separately.')
        y -= draw_lines(c, measure(c, intro, CW, 'Helvetica', 7.5), ML, y, 'Helvetica', 7.5, col('grey2'), 9.5)
        y -= 4*mm

        for k in kits:
            billing = str(k.get('billing', ''))
            purpose_lines = measure(c, k.get('purpose', ''), CW - 40*mm, 'Helvetica', 7)
            row_h = 6*mm + len(purpose_lines) * 8.5 + 3*mm
            y = need(y, row_h + 2*mm)

            nm = str(k.get('name', ''))
            text(c, nm, ML+2*mm, y-4.5*mm, 'Helvetica-Bold', 8.5, col('navy2'))
            nm_w = c.stringWidth(nm, 'Helvetica-Bold', 8.5)
            qty = k.get('quantity', 1)
            text(c, f'×{qty}', ML+2*mm+nm_w+3*mm, y-4.5*mm, 'Helvetica-Bold', 8.5, col('blue'))

            if billing:
                chargeable = 'chargeable' in billing.lower()
                bg = BILL_AMBER_BG if chargeable else BILL_GREEN_BG
                fg = BILL_AMBER_FG if chargeable else BILL_GREEN_FG
                c.setFont('Helvetica-Bold', 6.5)
                bwid = c.stringWidth(billing, 'Helvetica-Bold', 6.5) + 8
                pill(c, W-MR-bwid, y-6*mm, billing, bg, fg)

            if purpose_lines:
                draw_lines(c, purpose_lines, ML+2*mm, y-4.5*mm-8, 'Helvetica', 7, col('grey2'), 8.5)

            y -= row_h
            c.setStrokeColor(col('line')); c.setLineWidth(0.4)
            c.line(ML, y, W-MR, y)
            y -= 3*mm

        # Same running total the nurse saw on screen. Figures come from the plan
        # JSON rather than being recomputed, so the two cannot disagree.
        total   = supplies.get('kits_total', sum(k.get('quantity', 1) for k in kits))
        incl    = supplies.get('kits_included', min(total, allowance))
        extra   = supplies.get('kits_chargeable', max(0, total - allowance))
        bar_h = 8 * mm
        y = need(y, bar_h + 4*mm)
        fill_rect(c, ML, y-bar_h, CW, bar_h, col('grey_l'), radius=2*mm)
        head = f'{total} kits  ·  {incl} included  ·  '
        text(c, head, ML+4*mm, y-bar_h+2.9*mm, 'Helvetica', 8, col('grey2'))
        text(c, f'{extra} chargeable',
             ML+4*mm + c.stringWidth(head, 'Helvetica', 8), y-bar_h+2.9*mm,
             'Helvetica-Bold' if extra > 0 else 'Helvetica', 8,
             BILL_AMBER_FG if extra > 0 else col('grey2'))
        y -= bar_h + 4*mm

        if consumables:
            # Measure first so the label can never be stranded from its list
            cons_lines = measure(c, ', '.join(consumables), CW - 4*mm, 'Helvetica', 7.5)
            y = need(y, 7*mm + len(cons_lines) * 9.5 + 7*mm)
            text(c, 'ALSO PROVIDED', ML+2*mm, y-3*mm, 'Helvetica-Bold', 6, col('grey3'))
            y -= 7*mm
            y -= draw_lines(c, cons_lines, ML+2*mm, y, 'Helvetica', 7.5, col('grey2'), 9.5)
            y -= 4*mm

    # ══ PAGE 4 — SESSION RECORD SHEET ════════════════════════════════════
    y = new_page()
    y = section_header(c, y, 'YOUR CARE RECORD', col('navy2'), icon='◈')

    text(c, 'Your nurse will complete one row at each visit. Please keep this sheet '
            'with the care plan.', ML, y-1*mm, 'Helvetica', 7.5, col('grey2'))
    y -= 7*mm

    # Repeated here because this is the sheet that stays out and visible in the home
    if contact_bits:
        bar_h = 8 * mm
        fill_rect(c, ML, y - bar_h, CW, bar_h, col('blue_l'), radius=2*mm)
        text(c, '     '.join(contact_bits), ML + 4*mm, y - bar_h + 2.8*mm,
             'Helvetica-Bold', 7.5, col('navy2'))
        y -= bar_h + 4*mm

    # Column widths must sum to CW (180mm). Measure columns flex if there are many.
    fixed = {'session': 16*mm, 'date': 22*mm, 'bath': 12*mm,
             'exercise': 16*mm, 'meds': 12*mm, 'nurse': 18*mm}
    NOTES_MIN = 14 * mm
    meas = [measure_abbr(m.get('measure', '')) for m in mon]
    meas_w = 14 * mm
    fixed_total = sum(fixed.values())
    while meas and fixed_total + len(meas)*meas_w + NOTES_MIN > CW and meas_w > 10*mm:
        meas_w -= 0.5 * mm
    while meas and fixed_total + len(meas)*meas_w + NOTES_MIN > CW:
        dropped = meas.pop()
        print(f'note: record sheet omits the "{dropped}" column, no room at this width',
              file=sys.stderr)
    notes_w = CW - fixed_total - len(meas)*meas_w

    headers = ([('Session', fixed['session']), ('Date', fixed['date'])]
               + [(m, meas_w) for m in meas]
               + [('Bath', fixed['bath']), ('Exercise', fixed['exercise']),
                  ('Meds', fixed['meds']), ('Nurse', fixed['nurse']),
                  ('Notes', notes_w)])
    tick_cols = {'Bath', 'Exercise', 'Meds'}

    ROW_H = 8 * mm
    HEAD_H = 7 * mm
    ROWS_PER_PAGE = 15

    def draw_table_head(yy):
        fill_rect(c, ML, yy-HEAD_H, CW, HEAD_H, col('navy2'))
        cx = ML
        for label, wd in headers:
            text(c, label, cx + wd/2, yy-HEAD_H+2.4*mm, 'Helvetica-Bold', 6.5, white, 'center')
            cx += wd
        return yy - HEAD_H

    total_rows = int(plan.get('session_count') or 10)
    y = draw_table_head(y)
    drawn_on_page = 0

    for n in range(1, total_rows + 1):
        if drawn_on_page >= ROWS_PER_PAGE or y - ROW_H < FOOTER_H:
            y = new_page()
            y = draw_table_head(y)
            drawn_on_page = 0

        fill_rect(c, ML, y-ROW_H, CW, ROW_H, white if n % 2 else col('grey_l'))
        cx = ML
        c.setStrokeColor(col('line')); c.setLineWidth(0.4)
        for label, wd in headers:
            c.rect(cx, y-ROW_H, wd, ROW_H, fill=0, stroke=1)
            if label == 'Session':
                text(c, str(n), cx + wd/2, y-ROW_H+2.9*mm, 'Helvetica-Bold', 8,
                     col('navy2'), 'center')
            elif label in tick_cols:
                box = 3.5 * mm
                c.setStrokeColor(col('grey3')); c.setLineWidth(0.5)
                c.rect(cx + wd/2 - box/2, y - ROW_H/2 - box/2, box, box, fill=0, stroke=1)
                c.setStrokeColor(col('line')); c.setLineWidth(0.4)
            cx += wd
        y -= ROW_H
        drawn_on_page += 1

    draw_footer(c, page_num[0])
    c.save()
    return output_path


# ══ SAMPLE DATA ══════════════════════════════════════════════════════════
# Bedbound archetype — exercises every layout branch: four routine blocks,
# six care_explained cards, wrapping notes, both billing pill colours.
SAMPLE_PATIENT = {
    'name': 'Lakshmi Narayan',
    'age': 81,
    'gender': 'Female',
    'zone': 'Marathahalli',
    'care_type': 'Bedbound / high-dependency care',
    'service_tier': 'Advanced — 8 hours',
    'start_date': '15 Aug 2026',
    'assessed_by': 'Sr. Nurse Anjali',
    'date': 'Generated 11 Aug 2026',
}

SAMPLE_PLAN = {
    'service_tier': 'Advanced — 8 hours',
    'care_summary': (
        'Your nurse will be with you for eight hours each day to help with everything you '
        'cannot manage on your own while you are in bed. This includes washing, feeding '
        'through your tube, turning you regularly to protect your skin, and watching for any '
        'early sign of infection or breathing trouble. The plan below explains what happens '
        'at each visit and why, so you and your family always know what to expect.'
    ),
    'daily_routine': [
        {
            'block': 'Morning', 'time_range': '7:00 – 10:00 am',
            'tasks': [
                {'time': '7:00 am', 'task': 'Vitals check',
                 'note': 'Blood pressure, pulse, oxygen and temperature recorded on your care sheet before anything else, so your nurse knows how you are starting the day.'},
                {'time': '7:30 am', 'task': 'Position change',
                 'note': 'Turned onto your right side with a pillow supporting your back and another between your knees.'},
                {'time': '8:00 am', 'task': 'Bed bath and grooming',
                 'note': 'Warm water, mild soap, and your skin patted dry rather than rubbed. Hair combed and mouth cleaned afterwards.'},
                {'time': '9:00 am', 'task': 'Tube feed and medicines',
                 'note': 'Head of the bed raised first and kept raised for thirty minutes after the feed to stop anything coming back up.'},
                {'time': '9:45 am', 'task': 'Passive limb exercises',
                 'note': 'Slow bending and straightening of both arms and legs, ten times each, stopping if you show any sign of pain.'},
            ],
        },
        {
            'block': 'Midday', 'time_range': '10:00 am – 1:00 pm',
            'tasks': [
                {'time': '10:00 am', 'task': 'Position change',
                 'note': 'Turned onto your back with your heels lifted clear of the mattress on a soft pillow.'},
                {'time': '11:00 am', 'task': 'Pressure area check',
                 'note': 'Your nurse looks closely at your lower back, hips, heels and elbows for any redness that does not fade when pressed.'},
                {'time': '12:00 pm', 'task': 'Tube feed',
                 'note': 'Given slowly, with the tube flushed with water before and after.'},
                {'time': '12:45 pm', 'task': 'Breathing exercises',
                 'note': 'Deep breaths encouraged and held briefly, which helps keep the lower parts of your lungs open.'},
            ],
        },
        {
            'block': 'Afternoon', 'time_range': '1:00 – 4:00 pm',
            'tasks': [
                {'time': '1:00 pm', 'task': 'Position change',
                 'note': 'Turned onto your left side, with the same pillow support as the morning.'},
                {'time': '2:00 pm', 'task': 'Vitals check',
                 'note': 'Second reading of the day, compared against the morning figures to catch any drift early.'},
                {'time': '2:30 pm', 'task': 'Continence care',
                 'note': 'Pad changed, skin washed and a barrier cream applied to keep moisture off the skin.'},
                {'time': '3:30 pm', 'task': 'Rest and company',
                 'note': 'Quiet time with the room dimmed, and your nurse nearby if you want to talk.'},
            ],
        },
        {
            'block': 'Evening', 'time_range': '4:00 – 7:00 pm',
            'tasks': [
                {'time': '4:00 pm', 'task': 'Position change',
                 'note': 'Turned onto your right side again to complete the four-hourly cycle.'},
                {'time': '5:00 pm', 'task': 'Tube feed and medicines',
                 'note': 'Evening feed with the head of the bed raised, followed by your prescribed night medicines.'},
                {'time': '6:00 pm', 'task': 'Oral and skin care',
                 'note': 'Mouth cleaned with a soft swab and moisturiser applied to dry areas on your arms and legs.'},
                {'time': '6:45 pm', 'task': 'Handover notes',
                 'note': 'Your nurse writes the day on your record sheet and tells your family anything they need to watch overnight.'},
            ],
        },
    ],
    'care_explained': [
        {'task': 'Position change every 2 hours',
         'why': 'Lying in one position for too long presses the skin against the bone and cuts off the blood supply to it. Within a couple of hours that skin can begin to break down into a pressure sore, which is painful and slow to heal.',
         'how': 'Your nurse rolls you gently onto alternating sides using a pillow behind your back for support and another between your knees, so your weight moves to a different area each time.'},
        {'task': 'Bed bath and hygiene',
         'why': 'Washing keeps the skin clean and free of sweat and moisture that would otherwise soften it and make sores more likely. It is also the moment your nurse can see all of your skin properly.',
         'how': 'Warm water and mild soap, one section of the body at a time with the rest kept covered, and the skin patted dry rather than rubbed.'},
        {'task': 'Feeding through your tube',
         'why': 'Food given too quickly, or while you are lying flat, can come back up and go into your lungs. That causes a chest infection which is serious for someone who cannot cough strongly.',
         'how': 'The head of your bed is raised before the feed starts and stays raised for thirty minutes afterwards. The tube is flushed with water before and after, and the feed is given slowly.'},
        {'task': 'Pressure area care',
         'why': 'The first sign of a pressure sore is redness that does not fade when you press it. Caught at that stage it can be reversed completely; left alone it becomes an open wound.',
         'how': 'At every position change your nurse checks your lower back, hips, heels, elbows and the back of your head, and applies barrier cream where the skin looks at risk.'},
        {'task': 'Passive limb exercises',
         'why': 'Joints that are never moved slowly stiffen and shorten, until straightening the limb becomes painful or impossible. Moving them daily keeps them loose and helps the circulation.',
         'how': 'Your nurse supports the limb at two points and moves each joint slowly through its comfortable range, about ten times, stopping at once if you wince or resist.'},
        {'task': 'Mouth and oral care',
         'why': 'When you are not eating by mouth, saliva stops doing its usual cleaning job and bacteria build up quickly. Those bacteria can be breathed into the lungs and cause infection.',
         'how': 'A soft swab and clean water twice a day, with lip balm applied afterwards to stop your lips cracking.'},
    ],
    'exercise_plan': {
        'types': ['Passive limb exercises', 'Breathing exercises'],
        'frequency': 'Twice daily',
        'instructions': (
            'Passive bending and straightening of both knees and elbows, ten slow repetitions '
            'each, supporting the limb under the joint and above it. Ankle circles ten times in '
            'each direction to help the circulation in your legs. For breathing, encourage five '
            'deep breaths held for two seconds each, repeated three times with a rest in between. '
            'Do the limb exercises before the feed, not after.'
        ),
        'precautions': (
            'Stop immediately if you wince, pull away, or if your breathing becomes laboured. '
            'Never force a joint that resists. Do not carry out limb exercises within thirty '
            'minutes of a tube feed.'
        ),
    },
    'monitoring': [
        {'measure': 'Blood pressure', 'when': 'Morning and afternoon',
         'normal_range': 'Below 140/90', 'call_if': 'Above 160/100 or below 90/60'},
        {'measure': 'Pulse', 'when': 'Morning and afternoon',
         'normal_range': '60 to 100 a minute', 'call_if': 'Above 110 or below 50'},
        {'measure': 'Oxygen (SpO2)', 'when': 'Morning and afternoon',
         'normal_range': '95% or above', 'call_if': 'Below 92% on two readings'},
        {'measure': 'Temperature', 'when': 'Morning and afternoon',
         'normal_range': '36.5 to 37.5 °C', 'call_if': 'Above 38 °C or below 35.5 °C'},
    ],
    'safety_at_home': [
        'Keep the bed rails up whenever your nurse is not at the bedside, so there is no risk of rolling out.',
        'Keep the floor beside the bed clear and dry, especially where your family walks at night.',
        'Never leave you lying flat straight after a feed, as this is when food is most likely to come back up.',
        'Keep the suction machine plugged in and within reach of the bed at all times.',
        'Make sure the room has a working light your family can reach without crossing the room in the dark.',
    ],
    'contact_criteria': [
        'Call your nurse if your breathing becomes noisy, fast, or harder work than usual.',
        'Call if any redness on your skin does not fade within twenty minutes of turning.',
        'Call if you have a temperature above 38 °C, or you feel cold and shivery.',
        'Call if the feeding tube comes loose, blocks, or anything leaks around it.',
        'Call if you have not passed urine for eight hours, or your abdomen feels swollen and hard.',
    ],
    'escalation_pathway': 'Attending nurse → Lifetime Health clinical team',
    'supplies': {
        'kits': [
            {'name': 'Disposable kit', 'quantity': 1,
             'purpose': 'Gloves, apron and mask, used at every visit so nothing is carried from one home to another.',
             'billing': 'Included'},
            {'name': 'Bathing kit', 'quantity': 2,
             'purpose': 'Sponge, soap, towel and hygiene supplies for washing you in bed. A second kit is needed because you are washed twice a day.',
             'billing': '1 included, 1 chargeable'},
            {'name': 'Ryles tube feed kit', 'quantity': 1,
             'purpose': 'Feeding syringe, funnel and flush supplies for giving your feeds safely through the tube.',
             'billing': 'Included'},
        ],
        'consumables': [
            'Under pad', 'Sterile gloves', 'Normal saline 100ml',
            'Cotton balls', 'Micropore', 'Barrier cream',
        ],
    },
    'session_count': 10,
}


if __name__ == '__main__':
    if '--json' in sys.argv:
        idx = sys.argv.index('--json')
        data = json.loads(sys.argv[idx+1])
        generate_caregiver_pdf(data['patient'], data['plan'],
                               data.get('output', 'caregiver_plan.pdf'))
    elif '--help' in sys.argv:
        print(__doc__)
    else:
        output = os.path.join(os.path.dirname(__file__), 'sample_caregiver_plan.pdf')
        generate_caregiver_pdf(SAMPLE_PATIENT, SAMPLE_PLAN, output)
        print(f'Wrote {output}')
