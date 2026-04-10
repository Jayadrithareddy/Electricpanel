import streamlit as st
import math
import io
import svgwrite as svg
import base64

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from svglib.svglib import svg2rlg
from reportlab.graphics import renderPDF
from reportlab.platypus import PageBreak
from reportlab.pdfgen import canvas
import datetime

# ---------------- PAGE CONFIG ----------------
st.set_page_config(page_title="Professional Microgrid SLD Generator", layout="wide")

# ---------- UI STYLE (Premium Dark Theme) ----------
st.markdown("""
<style>
    .stApp {
        background: linear-gradient(135deg, #062a30, #020617);
        font-family: 'Inter', sans-serif;
    }
    .main-title {
        text-align: center;
        font-size: 42px;
        font-weight: 800;
        color: #c37c5a;
        margin-bottom: 30px;
        text-shadow: 0 0 20px rgba(195, 124, 91, 0.3);
    }
    .section-title {
        font-size: 22px;
        font-weight: 600;
        color: #19988b;
        margin-top: 25px;
        margin-bottom: 12px;
        border-bottom: 1px solid rgba(25, 152, 139, 0.2);
        padding-bottom: 5px;
    }
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3 {
        color: #062a30 !important;
        font-weight: 800 !important;
    }
    [data-testid="stExpander"] summary p,
    .streamlit-expanderHeader p {
        color: #062a30 !important;
        font-weight: 800 !important;
        font-size: 16px !important;
    }
    .stNumberInput label, .stSelectbox label,
    .stNumberInput label p, .stSelectbox label p {
        color: #1e293b !important;
        font-weight: 700 !important;
        font-size: 14px !important;
        opacity: 1 !important;
    }
    .stButton>button {
        background: linear-gradient(90deg, #19988b, #15803d);
        color: white;
        border: none;
        padding: 12px 30px;
        font-size: 16px;
        border-radius: 8px;
        font-weight: 700;
        transition: all 0.3s ease;
        box-shadow: 0 4px 15px rgba(25, 152, 139, 0.3);
    }
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(25, 152, 139, 0.5);
        background: linear-gradient(90deg, #187e6c, #19988b);
    }
    .result-card {
        background: rgba(6, 42, 48, 0.8);
        border: 1px solid rgba(195, 124, 91, 0.3);
        padding: 15px;
        border-radius: 12px;
        margin-bottom: 15px;
        backdrop-filter: blur(10px);
    }
    .warning-card {
        background: rgba(239, 68, 68, 0.1);
        border-left: 4px solid #ef4444;
        padding: 15px;
        border-radius: 8px;
        margin-bottom: 15px;
        color: #fca5a5;
    }
    .info-card {
        background: rgba(25, 152, 139, 0.1);
        border-left: 4px solid #19988b;
        padding: 15px;
        border-radius: 8px;
        margin-bottom: 15px;
        color: #93c5fd;
    }
    /* ── Metrics row styling ── */
    [data-testid="stMetric"] {
        background: rgba(6, 42, 48, 0.8);
        border: 1px solid rgba(195, 124, 91, 0.3);
        border-radius: 12px;
        padding: 16px 20px;
        backdrop-filter: blur(10px);
    }
    [data-testid="stMetricLabel"] p {
        color: #94a3b8 !important;
        font-size: 13px !important;
        font-weight: 600 !important;
        letter-spacing: 0.5px;
    }
    [data-testid="stMetricValue"] {
        color: #19988b !important;
        font-size: 22px !important;
        font-weight: 800 !important;
    }
</style>
<div class="main-title">Microgrid Panel SLD Generator</div>
""", unsafe_allow_html=True)

# ---------------- INPUTS (Sidebar & Main) ----------------
with st.sidebar:
    st.header("⚙️ Design Parameters")

    with st.expander("Capacity Inputs", expanded=True):
        solar_kw   = st.number_input("Solar (kWp)",    value=100, min_value=0)
        grid_kw    = st.number_input("Grid (kW)",       value=120, min_value=0)
        num_dg     = st.number_input("Number of DGs",   value=2,   min_value=0, max_value=4)
        dg_ratings = []
        if num_dg > 0:
            st.markdown(
                "<div style='font-size:13px;color:#64748b;margin-top:5px;margin-bottom:5px;'>"
                "DG Specifications</div>",
                unsafe_allow_html=True,
            )
            for i in range(int(num_dg)):
                dg = st.number_input(f"DG {i+1} Rating (kVA)", value=250, key=f"dg_in_{i}")
                dg_ratings.append(dg)

        num_outputs = st.number_input("Outgoing Feeders", value=3, min_value=1, max_value=10)
        mccb_outputs = []
        if num_outputs > 0:
            st.markdown(
                "<div style='font-size:13px;color:#64748b;margin-top:5px;margin-bottom:5px;'>"
                "Outgoing Feeder Specifications (Amperes)</div>",
                unsafe_allow_html=True,
            )
            for i in range(int(num_outputs)):
                default_val = 400 if i < 2 else 250
                out_r = st.number_input(
                    f"O/G {i+1} Rating (Amp)", value=default_val, key=f"og_in_{i}", min_value=0
                )
                mccb_outputs.append(out_r)

        busbar_material = st.selectbox("Busbar Material", ["Copper", "Aluminium"], index=1)
        num_poles       = st.selectbox("System Phases/Poles", [1, 2, 3, 4, 5], index=2)

    st.divider()
    submit = st.button("Generate Final SLD & BOM", use_container_width=True)

# ---------------- CORE CALCULATIONS ----------------
STANDARD_MCCBS = [16,20,25,32,40,50,63,80,100,125,160,200,250,315,400,500,630,800,1000,1250,1600]

def get_mccb_rating(current):
    required = current * 1.25
    for rating in STANDARD_MCCBS:
        if rating >= required:
            return rating
    return STANDARD_MCCBS[-1]

V  = 415
PF = 0.8

i_solar    = (solar_kw * 1000) / (math.sqrt(3) * V * PF) if solar_kw > 0 else 0
mccb_solar = get_mccb_rating(i_solar) if solar_kw > 0 else 0

i_grid    = (grid_kw * 1000) / (math.sqrt(3) * V * PF) if grid_kw > 0 else 0
mccb_grid = get_mccb_rating(i_grid) if grid_kw > 0 else 0

dg_mccbs    = []
dg_currents = []
for dg in dg_ratings:
    i = (dg * 1000) / (math.sqrt(3) * V * PF)
    dg_currents.append(i)
    dg_mccbs.append(get_mccb_rating(i))

total_busbar_current = i_solar + i_grid + sum(dg_currents)

density     = 1.6 if busbar_material == "Copper" else 1.0
busbar_area = total_busbar_current / density
suggested_width = math.ceil(busbar_area / 10 / 5) * 5
if suggested_width < 20:
    suggested_width = 20
busbar_spec = f"{suggested_width} x 10 mm {busbar_material}"

total_outgoing_rating = sum(mccb_outputs)

# ---------------- DRAWING HELPERS (SVG) ----------------

def draw_mccb(dwg, x, y, rating, poles, label, side="left"):
    dwg.add(dwg.line(start=(x, y - 50), end=(x, y - 18), stroke="white", stroke_width=2))
    dwg.add(dwg.line(start=(x, y + 12), end=(x, y + 50), stroke="white", stroke_width=2))
    dwg.add(dwg.path(
        d=f"M{x},{y-18} A14,14 0 0,0 {x+2},{y+12}",
        stroke="#10b981", fill="none", stroke_width=2.5,
    ))
    if side == "left":
        info_x, anchor        = x - 25, "end"
        label_x, label_anchor = x + 35, "start"
    else:
        info_x, anchor        = x + 25, "start"
        label_x, label_anchor = x - 35, "end"
    dwg.add(dwg.text(f"{rating}A, {poles}P", insert=(info_x, y - 5),
                     font_size=12, fill="#e2e8f0", text_anchor=anchor, font_family="Arial"))
    dwg.add(dwg.text("Motorised MCCB",       insert=(info_x, y + 12),
                     font_size=11, fill="#94a3b8", text_anchor=anchor, font_family="Arial"))
    dwg.add(dwg.text(label,                  insert=(label_x, y + 5),
                     font_size=14, font_weight="bold", fill="#f1f5f9",
                     text_anchor=label_anchor, font_family="Arial"))

def draw_tower(dwg, x, y):
    h = 60
    dwg.add(dwg.line((x,      y),      (x - 15, y + h), stroke="white", stroke_width=2))
    dwg.add(dwg.line((x,      y),      (x + 15, y + h), stroke="white", stroke_width=2))
    dwg.add(dwg.line((x - 15, y + h),  (x + 15, y + h), stroke="white", stroke_width=2))
    dwg.add(dwg.line((x - 10, y + 25), (x + 10, y + 25), stroke="white", stroke_width=1.5))
    dwg.add(dwg.line((x - 12, y + 45), (x + 12, y + 45), stroke="white", stroke_width=1.5))

def draw_solar(dwg, x, y):
    dwg.add(dwg.rect(insert=(x - 20, y + 10), size=(40, 45),
                     fill="#1e293b", stroke="white", stroke_width=1.5))
    for i in range(1, 4):
        dwg.add(dwg.line((x - 20, y + 10 + i * 11), (x + 20, y + 10 + i * 11),
                         stroke="white", stroke_opacity=0.5))
        dwg.add(dwg.line((x - 20 + i * 10, y + 10),  (x - 20 + i * 10, y + 55),
                         stroke="white", stroke_opacity=0.5))
    dwg.add(dwg.circle(center=(x - 30, y - 5), r=8,
                       stroke="#fbbf24", fill="none", stroke_width=2))

def draw_mgc(dwg, x, y):
    size = 100
    dwg.add(dwg.rect(insert=(x, y), size=(size, size),
                     fill="#1e1b4b", stroke="#a78bfa", stroke_width=3, rx=10))
    for i in range(5):
        off = 18 + i * 16
        dwg.add(dwg.line((x + off,    y - 10),        (x + off,    y),             stroke="#a78bfa", stroke_width=2))
        dwg.add(dwg.line((x + off,    y + size),       (x + off,    y + size + 10), stroke="#a78bfa", stroke_width=2))
        dwg.add(dwg.line((x - 10,     y + off),        (x,          y + off),       stroke="#a78bfa", stroke_width=2))
        dwg.add(dwg.line((x + size,   y + off),        (x + size + 10, y + off),    stroke="#a78bfa", stroke_width=2))
    dwg.add(dwg.text("MGC", insert=(x + size / 2, y + size / 2 + 8),
                     font_size=20, fill="white", font_weight="bold", text_anchor="middle"))

# ── DYNAMIC CANVAS SIZING ─────────────────────────────────────────────────────
def compute_canvas(n_dg, g_kw, s_kw, n_out):
    """
    Calculates canvas width, height, and column spacings so the diagram
    always fits every incomer and every outgoing feeder without overlap,
    regardless of how many the user chooses.
    """
    n_incomers = int(n_dg) + (1 if g_kw > 0 else 0) + (1 if s_kw > 0 else 0)
    n_incomers = max(n_incomers, 1)
    n_out      = max(int(n_out), 1)

    # Minimum px per column so labels / symbols never collide
    MIN_COL    = 280
    MARGIN_L   = 150   # left edge buffer
    MARGIN_R   = 200   # right edge buffer (MGC box needs ~160 px)

    # Raw width needed to fit each row independently
    inc_raw = MARGIN_L + n_incomers * MIN_COL + MARGIN_R
    out_raw = MARGIN_L + n_out      * MIN_COL + MARGIN_R

    width = max(inc_raw, out_raw, 900)   # never smaller than 900 px

    # Distribute columns evenly across usable width
    usable_inc = width - MARGIN_L - MARGIN_R
    usable_out = width - MARGIN_L - MARGIN_R
    inc_spacing = max(MIN_COL, usable_inc // n_incomers)
    out_spacing = max(MIN_COL, usable_out // n_out)

    # Height: fixed rhythm; grows when output labels need more vertical room
    height = 950

    return int(width), int(height), int(inc_spacing), int(out_spacing), int(MARGIN_L)


# ---------------- MAIN UI LOGIC ----------------
if submit:
    warning_flag = total_busbar_current > total_outgoing_rating

    st.markdown(f"""
    <div class="info-card">
        <strong>📊 Busbar Calculation Summary</strong><br>
        Total Busbar Current: <strong>{total_busbar_current:.2f}A</strong><br>
        Total Outgoing Rating: <strong>{total_outgoing_rating:.0f}A</strong><br>
        Recommended Busbar Size: <strong>{busbar_spec}</strong>
    </div>
    """, unsafe_allow_html=True)

    if warning_flag:
        st.markdown(f"""
        <div class="warning-card">
            <strong>⚠️ WARNING: Insufficient Outgoing Capacity</strong><br>
            Total busbar current (<strong>{total_busbar_current:.2f}A</strong>) exceeds total outgoing
            breaker rating (<strong>{total_outgoing_rating:.0f}A</strong>).<br>
            Please increase outgoing feeder ratings or review your system configuration.
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="info-card">
            ✅ System is properly sized. Outgoing feeders match source capacity.
        </div>
        """, unsafe_allow_html=True)

    # ── 1. GENERATE SLD SVG ──────────────────────────────────────────────────
    def generate_sld():
        # Compute dynamic layout
        width, height, inc_spacing, out_spacing, x_init = compute_canvas(
            num_dg, grid_kw, solar_kw, num_outputs
        )

        dwg = svg.Drawing(size=(width, height), profile="full")
        dwg.viewbox(0, 0, width, height)

        # Background
        dwg.add(dwg.rect((0, 0), (width, height),
                         fill="#020617", stroke="#334155", stroke_width=2, rx=15))

        # Proportional vertical landmarks
        y_division = int(height * 0.42)   # ~399 px at h=950
        y_sources  = int(height * 0.19)   # ~180 px
        y_busbar   = int(height * 0.67)   # ~636 px

        # Scope divider
        dwg.add(dwg.line((30, y_division), (width - 30, y_division),
                         stroke="#475569", stroke_width=1, stroke_dasharray="8,4"))
        dwg.add(dwg.text("CUSTOMER SCOPE",
                         insert=(width / 2, 50),
                         font_size=20, font_weight="bold", fill="#94a3b8", text_anchor="middle"))
        dwg.add(dwg.text("KIRLOSKAR SCOPE",
                         insert=(50, height - 40),
                         font_size=20, font_weight="bold", fill="#94a3b8"))
        dwg.add(dwg.text("Smart AMF Panel",
                         insert=(width - 220, height - 40),
                         font_size=18, fill="#6366f1"))

        # MGC — anchored to right side, below divider
        mgc_x = width - 155
        mgc_y = y_division + 10
        draw_mgc(dwg, mgc_x, mgc_y)
        dwg.add(dwg.text("Auto / Manual",
                         insert=(mgc_x - 10, mgc_y + 30),
                         font_size=13, fill="#cbd5e1", text_anchor="end"))

        current_x    = x_init
        active_ics_x = []
        ic_index     = 1

        # ── DGs ──────────────────────────────────────────────────────────────
        for i in range(int(num_dg)):
            cx = current_x
            dwg.add(dwg.text(f"{dg_ratings[i]} kVA",
                             insert=(cx, y_sources - 85),
                             font_size=16, font_weight="bold", fill="white", text_anchor="middle"))
            dwg.add(dwg.circle(center=(cx, y_sources), r=45,
                               stroke="#60a5fa", fill="none", stroke_width=2.5))
            dwg.add(dwg.text(f"DG {i+1}",
                             insert=(cx, y_sources + 7),
                             font_size=15, fill="white", text_anchor="middle"))
            # wire → synch controller → MCCB → busbar
            dwg.add(dwg.line((cx, y_sources + 45), (cx, y_division - 100),
                             stroke="white", stroke_width=2))
            dwg.add(dwg.rect(insert=(cx - 65, y_division - 100), size=(130, 40),
                             fill="#1e293b", stroke="#60a5fa", rx=5))
            dwg.add(dwg.text("Synch Controller",
                             insert=(cx, y_division - 75),
                             font_size=12, fill="white", text_anchor="middle"))
            dwg.add(dwg.line((cx, y_division - 60), (cx, y_division + 40),
                             stroke="white", stroke_width=2))
            draw_mccb(dwg, cx, y_division + 100, dg_mccbs[i], num_poles, f"I/C {ic_index}", "left")
            dwg.add(dwg.line((cx, y_division + 150), (cx, y_busbar),
                             stroke="white", stroke_width=2))

            active_ics_x.append(cx)
            current_x += inc_spacing
            ic_index  += 1

        # ── Grid ─────────────────────────────────────────────────────────────
        if grid_kw > 0:
            cx = current_x
            dwg.add(dwg.text(f"{grid_kw} kW",
                             insert=(cx, y_sources - 85),
                             font_size=16, font_weight="bold", fill="white", text_anchor="middle"))
            draw_tower(dwg, cx, y_sources - 30)
            dwg.add(dwg.line((cx, y_sources + 30), (cx, y_division + 40),
                             stroke="white", stroke_width=2))
            draw_mccb(dwg, cx, y_division + 100, mccb_grid, num_poles, f"I/C {ic_index}", "left")
            dwg.add(dwg.line((cx, y_division + 150), (cx, y_busbar),
                             stroke="white", stroke_width=2))
            active_ics_x.append(cx)
            current_x += inc_spacing
            ic_index  += 1

        # ── Solar ─────────────────────────────────────────────────────────────
        if solar_kw > 0:
            cx = current_x
            dwg.add(dwg.text(f"{solar_kw} kWp",
                             insert=(cx, y_sources - 85),
                             font_size=16, font_weight="bold", fill="white", text_anchor="middle"))
            draw_solar(dwg, cx, y_sources - 30)
            dwg.add(dwg.line((cx, y_sources + 25), (cx, y_division + 40),
                             stroke="white", stroke_width=2))
            draw_mccb(dwg, cx, y_division + 100, mccb_solar, num_poles, f"I/C {ic_index}", "left")
            dwg.add(dwg.line((cx, y_division + 150), (cx, y_busbar),
                             stroke="white", stroke_width=2))
            active_ics_x.append(cx)

        # ── Main Busbar ───────────────────────────────────────────────────────
        dwg.add(dwg.line((80, y_busbar), (width - 80, y_busbar),
                         stroke="#ef4444", stroke_width=7))
        dwg.add(dwg.text("MAIN BUSBAR",
                         insert=(100, y_busbar - 12),
                         font_size=13, fill="#f87171"))
        dwg.add(dwg.text(f"{total_busbar_current:.1f}A",
                         insert=(width - 100, y_busbar - 12),
                         font_size=13, fill="#f87171", text_anchor="end"))

        # ── Communication Lines ───────────────────────────────────────────────
        if active_ics_x:
            comm_y = y_division - 20
            dwg.add(dwg.line((active_ics_x[0], comm_y), (mgc_x, comm_y),
                             stroke="#a78bfa", stroke_width=1.2, stroke_dasharray="6,3"))
            dwg.add(dwg.text("Communication and Control Lines",
                             insert=(width / 2, comm_y - 14),
                             font_size=13, fill="#c4b5fd", text_anchor="middle"))
            for ax in active_ics_x:
                dwg.add(dwg.line((ax, comm_y), (ax, y_division + 40),
                                 stroke="#a78bfa", stroke_width=1, stroke_dasharray="4,2"))
            dwg.add(dwg.line((mgc_x, comm_y), (mgc_x, mgc_y + 25),
                             stroke="#a78bfa", stroke_width=1, stroke_dasharray="6,3"))

        # ── Outgoing Feeders — centred across the full canvas width ───────────
        n_out           = int(num_outputs)
        total_out_span  = (n_out - 1) * out_spacing
        x_out_start     = max(80, (width - total_out_span) // 2)

        for i in range(n_out):
            ox     = x_out_start + i * out_spacing
            rating = mccb_outputs[i] if i < len(mccb_outputs) else 250
            dwg.add(dwg.line((ox, y_busbar),       (ox, y_busbar + 40),  stroke="white", stroke_width=2))
            draw_mccb(dwg, ox, y_busbar + 100, rating, num_poles, f"O/G {i+1}", "right")
            dwg.add(dwg.line((ox, y_busbar + 150), (ox, height - 80),    stroke="white", stroke_width=2))

        return dwg.tostring(), width, height

    # ── 2. RENDER SLD ────────────────────────────────────────────────────────
    st.markdown('<div class="section-title">📋 Professional Single Line Diagram</div>',
                unsafe_allow_html=True)
    sld_svg, svg_width, svg_height = generate_sld()
    b64 = base64.b64encode(sld_svg.encode("utf-8")).decode("utf-8")
    st.markdown(
        f'<div style="background:#020617;padding:20px;border-radius:15px;border:1px solid #334155;">'
        f'<img src="data:image/svg+xml;base64,{b64}" style="width:100%;"></div>',
        unsafe_allow_html=True,
    )

    # ---------------- PDF UTILITIES ----------------
    class NumberedCanvas(canvas.Canvas):
        def __init__(self, *args, **kwargs):
            canvas.Canvas.__init__(self, *args, **kwargs)
            self._saved_page_states = []

        def showPage(self):
            self._saved_page_states.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            """Add page info to each page (Page X of Y)"""
            num_pages = len(self._saved_page_states)
            for state in self._saved_page_states:
                self.__dict__.update(state)
                self.draw_footer(num_pages)
                canvas.Canvas.showPage(self)
            canvas.Canvas.save(self)

        def draw_footer(self, page_count):
            self.saveState()
            
            # --- 1. Top Right Logo ---
            logo_path = "Kirloskar Oil Engine Logo.png"
            logo_w, logo_h = 100, 35
            # Position at top right corner, high enough to avoid heading overlap
            self.drawImage(logo_path, A4[0] - 45 - logo_w, A4[1] - 30 - logo_h, 
                           width=logo_w, height=logo_h, preserveAspectRatio=True, mask='auto')

            # --- 2. Footer Styling ---
            self.setFont("Helvetica", 8)
            self.setStrokeColor(colors.HexColor("#cbd5e1")) 
            self.setLineWidth(0.5)
            # Horizontal line above footer
            self.line(45, 50, A4[0] - 45, 50)
            
            # Footer Text
            self.setFillColor(colors.HexColor("#475569"))
            # Left: Company Name
            self.drawString(45, 35, "Kirloskar Oil Engines Ltd.")
            
            # Center: Dynamic Date and Time
            now = datetime.datetime.now().strftime("%d-%b-%Y %I:%M %p")
            self.drawCentredString(A4[0]/2.0, 35, f"Report Generated: {now}")
            
            # Right: Page number (Page X of Y)
            page_num = self.getPageNumber()
            self.drawRightString(A4[0] - 45, 35, f"Page {page_num} of {page_count}")
            
            self.restoreState()

    # ── 3. PDF BOM GENERATOR ─────────────────────────────────────────────────
    def generate_pdf_report():
        buffer = io.BytesIO()
        # Increased topMargin to 80 to prevent overlap with the logo
        doc = SimpleDocTemplate(buffer, pagesize=A4,
                                rightMargin=45, leftMargin=45,
                                topMargin=80, bottomMargin=45)
        styles = getSampleStyleSheet()

        title_style            = styles["Title"]
        title_style.fontSize   = 22
        title_style.textColor  = colors.HexColor("#c37c5a")
        title_style.alignment  = 1

        h2_style             = styles["Heading2"]
        h2_style.fontSize    = 16
        h2_style.textColor   = colors.HexColor("#19988b")
        h2_style.spaceBefore = 12
        h2_style.spaceAfter  = 8

        normal_style           = styles["Normal"]
        normal_style.fontSize  = 10
        normal_style.leading   = 13
        normal_style.alignment = 4

        story = []

        # Page 1 – System Overview & SLD
        story.append(Paragraph("Microgrid Panel Technical Report", title_style))
        story.append(Spacer(1, 15))

        story.append(Paragraph("1. System Overview", h2_style))
        grid_text  = f"<b>{grid_kw} kW</b> Grid supply, " if grid_kw > 0 else ""
        solar_text = f"and <b>{solar_kw} kWp</b> Solar PV" if solar_kw > 0 else ""
        description = (
            f"This report details the configuration and material requirements for a customized "
            f"Microgrid Panel. The system handles <b>{int(num_dg)} DG(s)</b>, "
            f"{grid_text}{solar_text}. "
            f"Managed via a centralized Microgrid Controller (MGC) for seamless power source management."
        )
        story.append(Paragraph(description, normal_style))
        story.append(Spacer(1, 12))

        story.append(Paragraph("2. System Specifications", h2_style))
        specs_text = (
            f"<b>Total Busbar Current Rating:</b> {total_busbar_current:.2f}A<br/>"
            f"<b>Total Outgoing Capacity:</b> {total_outgoing_rating:.0f}A<br/>"
            f"<b>Recommended Busbar:</b> {busbar_spec}<br/>"
            f"<b>System Configuration:</b> {int(num_poles)}-Phase, {int(num_outputs)} Outgoing Feeders<br/>"
            f"<b>Auto-computed Canvas:</b> {svg_width} × {svg_height} px"
        )
        if warning_flag:
            specs_text += (
                "<br/><font color='red'><b>WARNING:</b> Total busbar current exceeds total outgoing "
                "rating. Please review system configuration.</font>"
            )
        story.append(Paragraph(specs_text, normal_style))
        story.append(Spacer(1, 12))

        story.append(Paragraph("3. Single Line Diagram (SLD)", h2_style))
        with open("temp_sld.svg", "w", encoding="utf-8") as f:
            f.write(sld_svg)

        try:
            drawing        = svg2rlg("temp_sld.svg")
            drawing.width  = svg_width
            drawing.height = svg_height
            scale          = 505.0 / svg_width   # fit to A4 printable width
            drawing.scale(scale, scale)
            drawing.width  = svg_width  * scale
            drawing.height = svg_height * scale
            sld_table = Table([[drawing]], colWidths=[505])
            sld_table.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER")]))
            story.append(sld_table)
        except Exception as e:
            story.append(Paragraph(f"[Error rendering SLD: {str(e)}]", normal_style))

        story.append(Spacer(1, 20))
        story.append(Paragraph(
            "<i>Note: The diagram above illustrates the electrical topology and power flow "
            "between sources and outgoing feeders.</i>", normal_style))

        story.append(PageBreak())

        # Page 2 – Bill of Materials
        story.append(Paragraph("4. Bill Of Material (BOM)", h2_style))
        story.append(Spacer(1, 8))

        table_data = [["Sr No", "Component / Description", "Rating", "Poles", "Qty"]]
        sr = 1
        if solar_kw > 0:
            table_data.append([str(sr), "Solar Incomer MCCB",  f"{mccb_solar}A", f"{num_poles}P", "1"]); sr += 1
        if grid_kw > 0:
            table_data.append([str(sr), "Grid Incomer MCCB",   f"{mccb_grid}A",  f"{num_poles}P", "1"]); sr += 1
        for i, r in enumerate(dg_mccbs):
            table_data.append([str(sr), f"DG {i+1} Incomer MCCB", f"{r}A", f"{num_poles}P", "1"]); sr += 1
        for i, r in enumerate(mccb_outputs):
            table_data.append([str(sr), f"Outgoing Feeder (O/G {i+1})", f"{int(r)}A", f"{num_poles}P", "1"]); sr += 1
        table_data.append([str(sr), f"{busbar_material} Main Busbar",
                           f"{total_busbar_current:.1f}A Rated", "-", f"1 Set ({busbar_spec})"]); sr += 1
        table_data.append([str(sr), "Microgrid Controller (MGC)", "Standard", "-", "1"])

        # Optimized column widths: SrNo(30), Desc(150), Rating(90), Poles(45), Qty(190)
        table = Table(table_data, colWidths=[30, 150, 90, 45, 190])
        table.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, 0),  colors.HexColor("#19988b")),
            ("TEXTCOLOR",     (0, 0), (-1, 0),  colors.whitesmoke),
            ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
            ("FONTNAME",      (0, 0), (-1, 0),  "Helvetica-Bold"),
            ("BOTTOMPADDING", (0, 0), (-1, 0),  10),
            ("BACKGROUND",    (0, 1), (-1, -1), colors.HexColor("#f8fafc")),
            ("GRID",          (0, 0), (-1, -1), 0.5, colors.grey),
            ("FONTSIZE",      (0, 0), (-1, -1), 9),
            ("ROWBACKGROUNDS",(0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f5f9")]),
        ]))
        story.append(table)
        story.append(Spacer(1, 20))

        story.append(Paragraph("5. Notes & Remarks", h2_style))
        notes = (
            "• This Bill of Materials is subject to final design review and customer requirements.<br/>"
            "• All MCCB ratings include a 1.25x safety factor as per standard practice.<br/>"
            "• Busbar sizing considers thermal conductivity and current density limits.<br/>"
            "• The MGC provides automatic/manual source selection and switchover capability.<br/>"
            "• All components are to be sourced and installed as per relevant Indian Standards and IEC guidelines."
        )
        story.append(Paragraph(notes, normal_style))

        story.append(Paragraph(notes, normal_style))

        doc.build(story, canvasmaker=NumberedCanvas)
        buffer.seek(0)
        return buffer

    pdf_buffer = generate_pdf_report()
    st.download_button(
        label="📄 Download Technical Report (PDF)",
        data=pdf_buffer,
        file_name="Microgrid_Panel_Technical_Report.pdf",
        mime="application/pdf",
    )

    # ── 4. Summary metrics ────────────────────────────────────────────────────
    st.divider()
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Total Busbar Current",  f"{total_busbar_current:.2f}A")
    with col2:
        st.metric("Total Outgoing Rating", f"{total_outgoing_rating:.0f}A")
    with col3:
        st.metric("System Voltage",        "415V, 3Φ")
    with col4:
        st.metric("Busbar Size",           busbar_spec)
    with col5:
        st.metric("Canvas Size",           f"{svg_width} × {svg_height} px")
