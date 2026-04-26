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

def draw_footer(c, page_num):
    fill_rect(c, 0, 0, W, 11*mm, col('grey_l'))
    c.setStrokeColor(col('line')); c.setLineWidth(0.5); c.line(0, 11*mm, W, 11*mm)
    text(c, 'Lifetime Health  ·  lifetimehealth.in  ·  Confidential — for clinical use only',
         ML, 4*mm, size=6.5, color=col('grey3'))
    text(c, f'Page {page_num}', W-MR, 4*mm, size=6.5, color=col('grey3'), align='right')

PHASE_COLS  = [HexColor('#2563EB'), HexColor('#3B6FE8'), HexColor('#1A2744')]
PHASE_LIGHT = [HexColor('#EEF2FF'), HexColor('#DBEAFE'), HexColor('#EEF2FF')]

def generate_plan_pdf(patient, plan, output_path):
    c = rc.Canvas(output_path, pagesize=A4)

    # ── PAGE 1 ──────────────────────────────────────────────────────
    HDR = 63*mm
    gradient(c, 0, H-HDR, W, HDR, col('navy1'), col('navy2'))

    # Logo
    lx, ly = ML+9*mm, H-22*mm
    fill_rect(c, lx-9*mm, ly-9*mm, 18*mm, 18*mm, col('blue'), radius=9*mm)
    c.setStrokeColor(white); c.setLineWidth(2.2)
    c.line(lx, ly-5*mm, lx, ly+5*mm); c.line(lx-5*mm, ly, lx+5*mm, ly)

    text(c, 'Lifetime Health', ML+21*mm, H-18.5*mm, 'Helvetica-Bold', 16, white)
    text(c, 'Home Healthcare Platform  ·  Bangalore', ML+21*mm, H-26*mm, size=8, color=col('grey3'))

    bw = 50*mm
    fill_rect(c, W-MR-bw, H-23*mm, bw, 9*mm, col('blue'), radius=2*mm)
    text(c, 'TREATMENT PLAN', W-MR-bw/2, H-18.5*mm, 'Helvetica-Bold', 8, white, 'center')
    text(c, patient.get('date', 'Lifetime Health'), W-MR, H-29*mm, size=7.5, color=col('grey3'), align='right')

    name = patient.get('name', 'Patient')
    age  = patient.get('age', '')
    gender = patient.get('gender', '')
    zone = patient.get('zone', '')
    condition = patient.get('condition', '')

    text(c, name, ML, H-42*mm, 'Helvetica-Bold', 23, white)
    text(c, f"{age}{'y  ·  ' if age else ''}{gender}{'  ·  ' if gender else ''}{zone}", ML, H-50.5*mm, size=9.5, color=col('grey3'))

    # Condition tag
    c.setFont('Helvetica-Bold', 7.5)
    tw = c.stringWidth(condition, 'Helvetica-Bold', 7.5) + 10
    fill_rect(c, ML, H-61*mm, tw, 6.5*mm, col('navy2'), radius=2*mm)
    text(c, condition, ML+5, H-56.5*mm, 'Helvetica-Bold', 7.5, col('blue_l'))

    # Stat pills
    stats_y = H - HDR - 2*mm
    pill_h  = 18*mm
    pw = (CW - 7.5*mm) / 3
    pain_score = patient.get('pain_score', 5)
    pain_color = col('red') if pain_score >= 7 else (col('amber') if pain_score >= 4 else col('green'))
    stat_data = [
        ('PAIN SCORE', f"{pain_score}/10", '', col('grey_l'), pain_color),
        ('DURATION',   f"{plan.get('duration_weeks',8)}w", '', col('blue_l'), col('blue')),
        ('PACKAGE',    plan.get('package','Orthopedic')[:12], '', col('blue_l'), col('blue')),
    ]
    for i, (lbl, val, unit, bg, vc) in enumerate(stat_data):
        px = ML + i*(pw+2.5*mm)
        fill_rect(c, px, stats_y-pill_h, pw, pill_h, bg, radius=2.5*mm)
        text(c, lbl, px+4*mm, stats_y-5.5*mm, size=6.5, color=col('grey2'))
        text(c, val, px+4*mm, stats_y-13*mm, 'Helvetica-Bold', 14, vc)

    y = stats_y - pill_h - 4*mm

    # Clinical impression
    sec_h = 9.5*mm
    fill_rect(c, ML, y-sec_h, CW, sec_h, col('navy2'), radius=2.5*mm)
    text(c, '◈  CLINICAL IMPRESSION', ML+4*mm, y-sec_h+3.2*mm, 'Helvetica-Bold', 8.5, white)
    y -= sec_h + 2*mm

    imp_h = 18*mm
    fill_rect(c, ML, y-imp_h, CW, imp_h, col('blue_l'), radius=2*mm)
    fill_rect(c, ML, y-imp_h, 2.5*mm, imp_h, col('blue'), radius=1.5*mm)
    impression = plan.get('clinical_impression','')
    c.setFont('Helvetica', 8.5); c.setFillColor(col('grey1'))
    # Simple word wrap
    words = impression.split(); line_w = CW-10*mm; lines = []; lw = []
    for wd in words:
        test = ' '.join(lw+[wd])
        if c.stringWidth(test,'Helvetica',8.5) <= line_w: lw.append(wd)
        else:
            if lw: lines.append(' '.join(lw))
            lw = [wd]
    if lw: lines.append(' '.join(lw))
    ly2 = y - 5*mm
    for line in lines[:3]:
        c.drawString(ML+6*mm, ly2, line); ly2 -= 11

    y -= imp_h + 4*mm

    # Goals section header
    fill_rect(c, ML, y-sec_h, CW, sec_h, col('blue'), radius=2.5*mm)
    text(c, '◎  GOALS & VISIT PLAN', ML+4*mm, y-sec_h+3.2*mm, 'Helvetica-Bold', 8.5, white)
    y -= sec_h + 3*mm

    # Short-term goals
    short = plan.get('short_term_goals',[])
    long  = plan.get('long_term_goals',[])
    col_l = CW * 0.5
    for gi, (goals, lbl) in enumerate([(short,'Short-term'),(long,'Long-term')]):
        gx = ML + gi*col_l
        text(c, lbl, gx+2, y-4, 'Helvetica-Bold', 7.5, col('grey2'))
        gy = y - 4 - 9
        for g in goals[:3]:
            trunc = g[:45]+'...' if len(g)>45 else g
            text(c, '→ '+trunc, gx+2, gy, size=7.5, color=col('grey1')); gy -= 10

    y -= 45

    # Visit frequency
    vf_h = 8*mm
    fill_rect(c, ML, y-vf_h, CW, vf_h, col('blue_l'), radius=2*mm)
    c.setFont('Helvetica-Bold', 7.5); c.setFillColor(col('blue'))
    c.drawString(ML+4*mm, y-vf_h+2.5*mm, 'Visit plan:')
    c.setFont('Helvetica', 7.5); c.setFillColor(col('grey1'))
    c.drawString(ML+22*mm, y-vf_h+2.5*mm, plan.get('visit_frequency','')[:80])
    y -= vf_h + 4*mm

    # Metrics
    fill_rect(c, ML, y-sec_h, CW, sec_h, col('navy1'), radius=2.5*mm)
    text(c, '◉  KEY MEASUREMENTS', ML+4*mm, y-sec_h+3.2*mm, 'Helvetica-Bold', 8.5, white)
    y -= sec_h + 2*mm

    col_widths = [CW*0.38, CW*0.25, CW*0.25, CW*0.12]
    # Header row
    fill_rect(c, ML, y-8*mm, CW, 8*mm, col('navy1'))
    for ci, (lbl, cw2) in enumerate(zip(['Metric','Baseline','Target','Frequency'], col_widths)):
        cx = ML + sum(col_widths[:ci])
        text(c, lbl, cx+3, y-5.5*mm, 'Helvetica-Bold', 6.5, white)
    y -= 8*mm

    for mi, m in enumerate(plan.get('metrics',[])[:5]):
        row_bg = col('grey_l') if mi%2==0 else white
        fill_rect(c, ML, y-8*mm, CW, 8*mm, row_bg)
        vals = [m.get('name',''), m.get('baseline',''), m.get('target',''), m.get('frequency','')]
        colors = [col('grey1'), col('amber'), col('green'), col('grey2')]
        fonts  = ['Helvetica-Bold','Helvetica-Bold','Helvetica-Bold','Helvetica']
        for ci, (val, cw2, cc, fn) in enumerate(zip(vals, col_widths, colors, fonts)):
            cx = ML + sum(col_widths[:ci])
            trunc = val[:28]+'…' if len(val)>28 else val
            text(c, trunc, cx+3, y-5.5*mm, fn, 7, cc)
        y -= 8*mm

    draw_footer(c, 1)
    c.showPage()

    # ── PAGE 2 ──────────────────────────────────────────────────────
    HDR2 = 19*mm
    gradient(c, 0, H-HDR2, W, HDR2, col('navy1'), col('navy2'))
    lx2, ly2 = ML+6*mm, H-9.5*mm
    fill_rect(c, lx2-5*mm, ly2-5*mm, 10*mm, 10*mm, col('blue'), radius=5*mm)
    c.setStrokeColor(white); c.setLineWidth(1.5)
    c.line(lx2, ly2-3*mm, lx2, ly2+3*mm); c.line(lx2-3*mm, ly2, lx2+3*mm, ly2)
    text(c, 'Lifetime Health', ML+14*mm, H-8.5*mm, 'Helvetica-Bold', 10, white)
    text(c, f'Treatment Plan — {name}', ML+14*mm, H-15*mm, size=7.5, color=col('grey3'))

    y = H - HDR2 - 3*mm

    # Phases
    fill_rect(c, ML, y-sec_h, CW, sec_h, col('blue'), radius=2.5*mm)
    text(c, '▸  TREATMENT PHASES', ML+4*mm, y-sec_h+3.2*mm, 'Helvetica-Bold', 8.5, white)
    y -= sec_h + 3*mm

    for i, phase in enumerate(plan.get('phases',[])[:3]):
        pc = PHASE_COLS[i] if i < len(PHASE_COLS) else PHASE_COLS[-1]
        pl = PHASE_LIGHT[i]   if i < len(PHASE_LIGHT)   else PHASE_LIGHT[-1]
        ex_count = len(phase.get('exercises',[]))
        card_h = 11*mm + 7*mm + ex_count*9.5*mm + 9*mm

        if y - card_h < 14*mm:
            draw_footer(c, 2); c.showPage()
            gradient(c, 0, H-HDR2, W, HDR2, col('navy1'), col('navy2'))
            y = H - HDR2 - 5*mm

        # Phase header
        fill_rect(c, ML, y-11*mm, CW, 11*mm, pc, radius=2*mm)
        text(c, f"Phase {phase.get('number',i+1)}  —  {phase.get('name','')}", ML+4*mm, y-7*mm, 'Helvetica-Bold', 9.5, white)
        text(c, f"{phase.get('week_range','')}   ·   {phase.get('visit_frequency','')}", W-MR-4, y-7*mm, size=7.5, color=HexColor('#C0D8FF'), align='right')

        # Goals
        fill_rect(c, ML+2.5*mm, y-11*mm-7*mm, CW-2.5*mm, 7*mm, pl)
        text(c, 'Goals:', ML+5.5*mm, y-11*mm-4.5*mm, 'Helvetica-Bold', 6.5, pc)
        goals_str = '  ·  '.join(phase.get('goals',[])[:3])
        text(c, goals_str[:90], ML+18*mm, y-11*mm-4.5*mm, size=6.5, color=col('grey1'))

        # Exercises
        ey = y - 11*mm - 7*mm
        for ei, ex in enumerate(phase.get('exercises',[])[:5]):
            row_bg = white if ei%2==0 else col('grey_l')
            fill_rect(c, ML+2.5*mm, ey-9.5*mm, CW-2.5*mm, 9.5*mm, row_bg)
            fill_rect(c, ML+5.5*mm, ey-5.5*mm, 3, 3, pc, radius=1.5)
            text(c, ex.get('name',''), ML+9.5*mm, ey-4.5*mm, 'Helvetica-Bold', 8, col('grey1'))
            text(c, ex.get('prescription',''), ML+9.5*mm, ey-9*mm, size=7, color=col('grey2'))
            c.setStrokeColor(col('line')); c.setLineWidth(0.3); c.line(ML+2.5*mm, ey-9.5*mm, ML+CW, ey-9.5*mm)
            ey -= 9.5*mm

        # Footer
        fill_rect(c, ML+2.5*mm, ey-9*mm, CW-2.5*mm, 9*mm, col('grey_l'))
        text(c, 'Modalities:', ML+5.5*mm, ey-4.5*mm, 'Helvetica-Bold', 6.5, col('grey2'))
        text(c, phase.get('modalities','')[:60], ML+24*mm, ey-4.5*mm, size=6.5, color=col('grey2'))
        text(c, '⚠ '+phase.get('precautions','')[:70], ML+5.5*mm, ey-9*mm+1.5, size=6.5, color=col('amber'))

        # Left accent
        c.setStrokeColor(pc); c.setLineWidth(2)
        c.line(ML, y-card_h, ML, y)
        y -= card_h + 3.5*mm

    # Red flags + advice
    half = (CW - 5*mm) / 2
    flags  = plan.get('red_flags',[])
    advice = plan.get('home_advice',[])

    def list_box(cx, cy, w2, title, items, hc, bg, icon):
        item_h = 7.5*mm; hdr_h = 7.5*mm
        total_h = hdr_h + len(items[:5]) * item_h + 2*mm
        fill_rect(c, cx, cy-total_h, w2, total_h, HexColor(bg), radius=2*mm)
        fill_rect(c, cx, cy-hdr_h, w2, hdr_h, HexColor(hc), radius=2*mm)
        fill_rect(c, cx, cy-hdr_h, w2, hdr_h/2, HexColor(hc))
        text(c, title, cx+4*mm, cy-hdr_h+2.5*mm, 'Helvetica-Bold', 7.5, white)
        iy = cy - hdr_h - 1.5*mm
        for item in items[:5]:
            text(c, icon+' '+item[:50], cx+3*mm, iy-5*mm, size=7, color=HexColor(bg.replace('FE','12').replace('F0','14').replace('DC','79')))
            iy -= item_h
        return total_h

    if y > 40*mm:
        fh1 = list_box(ML, y, half, '⚑  RED FLAGS', flags, 'DC2626', 'FEE2E2', '▸')
        list_box(ML+half+5*mm, y, half, '✓  HOME ADVICE', advice, '3B6FE8', 'EEF2FF', '✓')
        y -= max(fh1, 0) + 4*mm

    draw_footer(c, 2)
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
    'date': '29 March 2026'
}

SAMPLE_PLAN = {
    'clinical_impression': 'Post-TKR patient at Day 12 with moderate pain (6/10), knee flexion limited to 65°, and partial weight-bearing on a walker. Diabetes mellitus elevates infection and healing risk. Priority: swelling control before progressive loading.',
    'short_term_goals': ['Reduce pain to ≤3/10 within 2 weeks','Achieve 90° knee flexion','Safe independent transfers'],
    'long_term_goals': ['Independent walking without aid by Week 10','Return to full household activities'],
    'duration_weeks': 10,
    'visit_frequency': '5x/week (Wk 1–2), 3x/week (Wk 3–6), 2x/week (Wk 7+)',
    'phases': [
        {
            'number':1, 'name':'Pain Control & Protection', 'week_range':'Week 1–2',
            'goals':['Reduce swelling','Initiate gentle ROM','Safe transfers'],
            'exercises':[
                {'name':'Ankle pumps','prescription':'20 reps every 2 hrs — DVT prevention'},
                {'name':'Quad sets (isometric)','prescription':'10 reps × 3 sets, 2x daily'},
                {'name':'Heel slides','prescription':'10 reps × 2 sets, 2x daily'},
                {'name':'Straight leg raises','prescription':'10 reps × 3 sets'},
                {'name':'Assisted knee flexion','prescription':'5 reps × 2 sets, to comfort only'},
            ],
            'modalities':'Ice 15 min post-session — no TENS/US Week 1',
            'precautions':'No forced flexion. Full WB only with walker.'
        },
        {
            'number':2, 'name':'Mobility & Strengthening', 'week_range':'Week 3–6',
            'goals':['Achieve 110° flexion','Independent transfers','Stairs with rail'],
            'exercises':[
                {'name':'Short arc quads','prescription':'15 reps × 3 sets'},
                {'name':'Mini squats (0–45°)','prescription':'10 reps × 3 sets'},
                {'name':'Step-ups (low step)','prescription':'10 reps × 2 sets each leg'},
                {'name':'Standing hip abduction','prescription':'15 reps × 3 sets'},
                {'name':'Gait training','prescription':'Walker → walking stick progression'},
            ],
            'modalities':'TENS 20 min if pain ≥4/10',
            'precautions':'No knee valgus in squats. Avoid deep flexion >90° until Wk 5.'
        },
        {
            'number':3, 'name':'Function & Return to Activity', 'week_range':'Week 7–10',
            'goals':['Walk 500m independently','Full household ADLs','Floor-to-stand'],
            'exercises':[
                {'name':'Leg press (bodyweight)','prescription':'15 reps × 3 sets'},
                {'name':'Single-leg balance','prescription':'30 sec × 3 each side'},
                {'name':'Full stair training','prescription':'Up/down without rail'},
                {'name':'Car transfer practice','prescription':'ADL training'},
                {'name':'Outdoor walking','prescription':'10 min → 30 min progressive'},
            ],
            'modalities':'Modalities only as needed for symptom management',
            'precautions':'Stop if pain >4/10. Report any pop or click immediately.'
        }
    ],
    'metrics': [
        {'name':'Pain Score (NRS)','baseline':'6/10','target':'≤2/10','frequency':'Every session'},
        {'name':'Knee Flexion ROM','baseline':'65°','target':'≥120°','frequency':'Every 7 visits'},
        {'name':'KOOS-12 Score','baseline':'28/100','target':'≥65/100','frequency':'Every 7 visits'},
        {'name':'Blood Glucose','baseline':'Check at first visit','target':'80–180 mg/dL','frequency':'Every session (diabetic)'},
    ],
    'red_flags': [
        'Sudden severe pain or audible pop in knee',
        'Spreading redness, heat or swelling increase',
        'Fever >38.5°C — infection risk elevated in diabetic patient',
        'Blood glucose <70 or >300 mg/dL at any visit',
        'Numbness, tingling or colour change in foot',
    ],
    'home_advice': [
        'Ice knee 15 min after every exercise session',
        'Keep leg elevated when resting to reduce swelling',
        'Daily blood sugar monitoring — share readings with care team',
        'High protein diet (eggs, dal, paneer) — accelerates healing',
        'Do not skip Week 1–2 sessions — continuity is critical',
    ],
    'package': 'Senior Citizen'
}


if __name__ == '__main__':
    if '--json' in sys.argv:
        idx = sys.argv.index('--json')
        data = json.loads(sys.argv[idx+1])
        generate_plan_pdf(data['patient'], data['plan'], data.get('output','plan.pdf'))
    elif '--help' in sys.argv:
        print(__doc__)
    else:
        output = os.path.join(os.path.dirname(__file__), 'sample_plan.pdf')
        generate_plan_pdf(SAMPLE_PATIENT, SAMPLE_PLAN, output)
