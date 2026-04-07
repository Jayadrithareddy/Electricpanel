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

# ---------------- PAGE CONFIG ----------------
st.set_page_config(page_title="Professional Microgrid SLD Generator", layout="wide")

# ---------- UI STYLE (Premium Dark Theme) ----------
st.markdown("""
<style>
    .stApp {
        background: linear-gradient(135deg, #020617, #0f172a);
        font-family: 'Inter', sans-serif;
    }
    .main-title {
        text-align: center;
        font-size: 42px;
        font-weight: 800;
        color: #a78bfa;
        margin-bottom: 30px;
        text-shadow: 0 0 20px rgba(167, 139, 250, 0.3);
    }
    .section-title {
        font-size: 22px;
        font-weight: 600;
        color: #c4b5fd;
        margin-top: 25px;
        margin-bottom: 12px;
        border-bottom: 1px solid rgba(196, 181, 253, 0.2);
        padding-bottom: 5px;
    }
    /* Sidebar Headers and Titles */
    [data-testid="stSidebar"] h1, 
    [data-testid="stSidebar"] h2, 
    [data-testid="stSidebar"] h3 {
        color: #0f172a !important;
        font-weight: 800 !important;
    }
    
    /* Expander Title styling for Capacity Inputs */
    [data-testid="stExpander"] summary p,
    .streamlit-expanderHeader p {
        color: #0f172a !important;
        font-weight: 800 !important;
        font-size: 16px !important;
    }

    /* All Parameter Labels to have darker readable color */
    .stNumberInput label, .stSelectbox label,
    .stNumberInput label p, .stSelectbox label p {
        color: #1e293b !important;
        font-weight: 700 !important;
        font-size: 14px !important;
        opacity: 1 !important;
    }
    .stButton>button {
        background: linear-gradient(90deg, #7c3aed, #6d28d9);
        color: white;
        border: none;
        padding: 12px 30px;
        font-size: 16px;
        border-radius: 8px;
        font-weight: 700;
        transition: all 0.3s ease;
        box-shadow: 0 4px 15px rgba(124, 58, 237, 0.3);
    }
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(124, 58, 237, 0.5);
        background: linear-gradient(90deg, #8b5cf6, #7c3aed);
    }
    .result-card {
        background: rgba(15, 23, 42, 0.8);
        border: 1px solid rgba(124, 58, 237, 0.3);
        padding: 15px;
        border-radius: 12px;
        margin-bottom: 15px;
        backdrop-filter: blur(10px);
    }
</style>
<div class="main-title">Microgrid Panel SLD Generator</div>
""", unsafe_allow_html=True)

# ---------------- INPUTS (Sidebar & Main) ----------------
with st.sidebar:
    st.header("⚙️ Design Parameters")
    
    with st.expander("Capacity Inputs", expanded=True):
        solar_kw = st.number_input("Solar (kWp)", value=100, min_value=0)
        grid_kw = st.number_input("Grid (kW)", value=120, min_value=0)
        num_dg = st.number_input("Number of DGs", value=2, min_value=0, max_value=4)
        dg_ratings = []
        if num_dg > 0:
            st.markdown(
                "<div style='font-size:13px; color:#64748b; margin-top:5px; margin-bottom:5px;'>DG Specifications</div>",
                unsafe_allow_html=True
            )
            for i in range(int(num_dg)):
                dg = st.number_input(f"DG {i+1} Rating (kVA)", value=250, key=f"dg_in_{i}")
                dg_ratings.append(dg)
        num_outputs = st.number_input("Outgoing Feeders", value=3, min_value=1, max_value=10)
        mccb_outputs = []
        if num_outputs > 0:
            st.markdown("<div style='font-size:13px; color:#64748b; margin-top:5px; margin-bottom:5px;'>Outgoing Specifications</div>", unsafe_allow_html=True)
            for i in range(int(num_outputs)):
                default_val = 400 if i < 2 else 250
                out_r = st.number_input(f"O/G {i+1} Rating (Amp)", value=default_val, key=f"og_in_{i}")
                mccb_outputs.append(out_r)

        busbar_material = st.selectbox("Busbar Material", ["Copper", "Aluminium"], index=1)
        num_poles = st.selectbox("System Phases/Poles", [1, 2, 3, 4, 5], index=1)

    st.divider()
    submit = st.button("Generate Final SLD & BOM")

# ---------------- CORE CALCULATIONS ----------------
STANDARD_MCCBS = [16,20,25,32,40,50,63,80,100,125,160,200,250,315,400,500,630,800,1000,1250,1600]

def get_mccb_rating(current):
    required = current * 1.25  # Safety factor
    for rating in STANDARD_MCCBS:
        if rating >= required:
            return rating
    return STANDARD_MCCBS[-1]

V = 415
PF = 0.8
# Power Factor logic: I = P / (sqrt(3) * V * PF)

# Incomer currents
i_solar = (solar_kw*1000)/(math.sqrt(3)*V*PF) if solar_kw > 0 else 0
mccb_solar = get_mccb_rating(i_solar) if solar_kw > 0 else 0

i_grid = (grid_kw*1000)/(math.sqrt(3)*V*PF) if grid_kw > 0 else 0
mccb_grid = get_mccb_rating(i_grid) if grid_kw > 0 else 0

dg_mccbs = []
dg_currents = []
for dg in dg_ratings:
    # User's logic: I = kVA*1000 / (sqrt(3) * V * PF)
    i = (dg*1000)/(math.sqrt(3)*V*PF)
    dg_currents.append(i)
    dg_mccbs.append(get_mccb_rating(i))

# Output logic
total_i = i_solar + i_grid + sum(dg_currents)

# Busbar Sizing
density = 1.6 if busbar_material == "Copper" else 1.0
busbar_area = total_i / density

# Recommended size suggestion (e.g. Width x 10mm)
suggested_width = math.ceil(busbar_area / 10 / 5) * 5 # Round up to nearest 5mm width for 10mm thickness
if suggested_width < 20: suggested_width = 20
busbar_spec = f"{suggested_width} x 10 mm {busbar_material}"

# --- FLAG/WARNING CHECK ---
sum_outgoing_rating = sum(mccb_outputs)
if total_i > sum_outgoing_rating:
    st.warning(f"⚠️ **Caution:** Total source/busbar current ({total_i:.2f}A) is higher than the total outgoing breaker rating ({sum_outgoing_rating}A). The outgoing breaker rating is lesser than total current.")

# ---------------- DRAWING HELPERS (SVG) ----------------

def draw_mccb(dwg, x, y, rating, poles, label, side="left"):
    # Main vertical lines (ensure break for symbol)
    dwg.add(dwg.line(start=(x, y-50), end=(x, y-18), stroke="white", stroke_width=2))
    dwg.add(dwg.line(start=(x, y+12), end=(x, y+50), stroke="white", stroke_width=2))
    
    # Breaker Arc Symbol (Standard SLD)
    dwg.add(dwg.path(
        d=f"M{x},{y-18} A14,14 0 0,0 {x+2},{y+12}",
        stroke="#10b981", fill="none", stroke_width=2.5
    ))
    
    # Information Text Alignment (FIXED OVERLAP)
    # Using specific offsets and text-anchors to prevent crossing the vertical line
    if side == "left":
        info_x = x - 25
        anchor = "end"
        label_x = x + 35
        label_anchor = "start"
    else:
        info_x = x + 25
        anchor = "start"
        label_x = x - 35
        label_anchor = "end"
        
    dwg.add(dwg.text(f"{rating}A, {poles}P", insert=(info_x, y-5), font_size=12, fill="#e2e8f0", text_anchor=anchor, font_family="Arial"))
    dwg.add(dwg.text("Motorised MCCB", insert=(info_x, y+12), font_size=11, fill="#94a3b8", text_anchor=anchor, font_family="Arial"))
    dwg.add(dwg.text(label, insert=(label_x, y+5), font_size=14, font_weight="bold", fill="#f1f5f9", text_anchor=label_anchor, font_family="Arial"))

def draw_tower(dwg, x, y):
    h = 60
    dwg.add(dwg.line((x, y), (x-15, y+h), stroke="white", stroke_width=2))
    dwg.add(dwg.line((x, y), (x+15, y+h), stroke="white", stroke_width=2))
    dwg.add(dwg.line((x-15, y+h), (x+15, y+h), stroke="white", stroke_width=2))
    dwg.add(dwg.line((x-10, y+25), (x+10, y+25), stroke="white", stroke_width=1.5))
    dwg.add(dwg.line((x-12, y+45), (x+12, y+45), stroke="white", stroke_width=1.5))

def draw_solar(dwg, x, y):
    # Panel
    dwg.add(dwg.rect(insert=(x-20, y+10), size=(40, 45), fill="#1e293b", stroke="white", stroke_width=1.5))
    for i in range(1, 4):
        dwg.add(dwg.line((x-20, y+10+i*11), (x+20, y+10+i*11), stroke="white", stroke_opacity=0.5))
        dwg.add(dwg.line((x-20+i*10, y+10), (x-20+i*10, y+55), stroke="white", stroke_opacity=0.5))
    # Sun
    dwg.add(dwg.circle(center=(x-30, y-5), r=8, stroke="#fbbf24", fill="none", stroke_width=2))

def draw_mgc(dwg, x, y):
    size = 100
    dwg.add(dwg.rect(insert=(x, y), size=(size, size), fill="#1e1b4b", stroke="#a78bfa", stroke_width=3, rx=10))
    for i in range(5):
        off = 18 + i*16
        dwg.add(dwg.line((x+off, y-10), (x+off, y), stroke="#a78bfa", stroke_width=2))
        dwg.add(dwg.line((x+off, y+size), (x+off, y+size+10), stroke="#a78bfa", stroke_width=2))
        dwg.add(dwg.line((x-10, y+off), (x, y+off), stroke="#a78bfa", stroke_width=2))
        dwg.add(dwg.line((x+size, y+off), (x+size+10, y+off), stroke="#a78bfa", stroke_width=2))
    dwg.add(dwg.text("MGC", insert=(x+size/2, y+size/2+8), font_size=20, fill="white", font_weight="bold", text_anchor="middle"))

# ---------------- MAIN UI LOGIC ----------------
if submit:
    # 1. GENERATE SLD SVG
    def generate_sld():
        width, height = 1450, 850
        dwg = svg.Drawing(size=(width, height), profile='full')
        dwg.viewbox(0, 0, width, height)
        
        # Border & Title Frame
        dwg.add(dwg.rect((0, 0), (width, height), fill="#020617", stroke="#334155", stroke_width=2, rx=15))
        
        y_division = 380
        dwg.add(dwg.line((30, y_division), (width-30, y_division), stroke="#475569", stroke_width=1, stroke_dasharray="8,4"))
        
        # Scope Labels
        dwg.add(dwg.text("CUSTOMER SCOPE", insert=(width/2, 50), font_size=20, font_weight="bold", fill="#94a3b8", text_anchor="middle"))
        dwg.add(dwg.text("KIRLOSKAR SCOPE", insert=(50, height-50), font_size=20, font_weight="bold", fill="#94a3b8"))
        dwg.add(dwg.text("Smart AMF Panel", insert=(width-220, height-50), font_size=18, fill="#6366f1"))

        y_sources = 180
        y_busbar = 600
        x_init = 220
        spacing = 280   # INCREASED SPACING TO PREVENT OVERLAP
        
        current_x = x_init
        
        # --- SOURCES ---
        active_ics_x = []
        
        # DGs
        for i in range(int(num_dg)):
            # Rating
            dwg.add(dwg.text(f"{dg_ratings[i]} kVA", insert=(current_x, y_sources - 85), font_size=16, font_weight="bold", fill="white", text_anchor="middle"))
            # Symbol
            dwg.add(dwg.circle(center=(current_x, y_sources), r=45, stroke="#60a5fa", fill="none", stroke_width=2.5))
            dwg.add(dwg.text(f"DG {i+1}", insert=(current_x, y_sources + 7), font_size=15, fill="white", text_anchor="middle"))
            # Wiring
            dwg.add(dwg.line((current_x, y_sources+45), (current_x, y_division - 100), stroke="white", stroke_width=2))
            # SC Box
            dwg.add(dwg.rect(insert=(current_x-65, y_division-100), size=(130, 40), fill="#1e293b", stroke="#60a5fa", rx=5))
            dwg.add(dwg.text("Synch Controller", insert=(current_x, y_division-75), font_size=12, fill="white", text_anchor="middle"))
            dwg.add(dwg.line((current_x, y_division-60), (current_x, y_division + 40), stroke="white", stroke_width=2))
            # MCCB
            draw_mccb(dwg, current_x, y_division + 100, dg_mccbs[i], num_poles, f"I/C {i+1}", "left")
            dwg.add(dwg.line((current_x, y_division+150), (current_x, y_busbar), stroke="white", stroke_width=2))
            
            active_ics_x.append(current_x)
            current_x += spacing

        # Grid
        if grid_kw > 0:
            dwg.add(dwg.text(f"{grid_kw} kW", insert=(current_x, y_sources - 85), font_size=16, font_weight="bold", fill="white", text_anchor="middle"))
            draw_tower(dwg, current_x, y_sources - 30)
            dwg.add(dwg.line((current_x, y_sources + 30), (current_x, y_division + 40), stroke="white", stroke_width=2))
            draw_mccb(dwg, current_x, y_division + 100, mccb_grid, num_poles, "I/C 3", "left")
            dwg.add(dwg.line((current_x, y_division + 150), (current_x, y_busbar), stroke="white", stroke_width=2))
            active_ics_x.append(current_x)
            current_x += spacing

        # Solar
        if solar_kw > 0:
            dwg.add(dwg.text(f"{solar_kw} kWp", insert=(current_x, y_sources - 85), font_size=16, font_weight="bold", fill="white", text_anchor="middle"))
            draw_solar(dwg, current_x, y_sources - 30)
            dwg.add(dwg.line((current_x, y_sources + 25), (current_x, y_division + 40), stroke="white", stroke_width=2))
            draw_mccb(dwg, current_x, y_division + 100, mccb_solar, num_poles, "I/C 4", "left")
            dwg.add(dwg.line((current_x, y_division + 150), (current_x, y_busbar), stroke="white", stroke_width=2))
            active_ics_x.append(current_x)

        # --- BUSBAR ---
        dwg.add(dwg.line((100, y_busbar), (width-100, y_busbar), stroke="#ef4444", stroke_width=7))
        dwg.add(dwg.text("MAIN BUSBAR", insert=(110, y_busbar-10), font_size=12, fill="#f87171"))
        
        # --- MGC & COMM ---
        mgc_x, mgc_y = width - 160, y_division + 10
        draw_mgc(dwg, mgc_x, mgc_y)
        dwg.add(dwg.text("Auto / Manual", insert=(mgc_x - 15, mgc_y + 30), font_size=13, fill="#cbd5e1", text_anchor="end"))
        
        # Communication Lines (Non-overlapping positions)
        comm_y = y_division - 20
        dwg.add(dwg.line((active_ics_x[0], comm_y), (mgc_x, comm_y), stroke="#a78bfa", stroke_width=1.2, stroke_dasharray="6,3"))
        dwg.add(dwg.text("Communication and Control Lines", insert=(width/2, comm_y - 12), font_size=13, fill="#c4b5fd", text_anchor="middle"))
        for ax in active_ics_x:
            dwg.add(dwg.line((ax, comm_y), (ax, y_division + 40), stroke="#a78bfa", stroke_width=1, stroke_dasharray="4,2"))
        dwg.add(dwg.line((mgc_x, comm_y), (mgc_x, mgc_y + 25), stroke="#a78bfa", stroke_width=1, stroke_dasharray="6,3"))

        # --- OUTPUTS ---
        x_out_start = 280
        out_spacing = 300
        for i in range(int(num_outputs)):
            ox = x_out_start + i*out_spacing
            if ox > width - 150: break # Safety check
            rating = mccb_outputs[i] if i < len(mccb_outputs) else 250
            dwg.add(dwg.line((ox, y_busbar), (ox, y_busbar + 40), stroke="white", stroke_width=2))
            draw_mccb(dwg, ox, y_busbar + 100, rating, num_poles, f"O/G {i+1}", "right")
            dwg.add(dwg.line((ox, y_busbar + 150), (ox, height - 100), stroke="white", stroke_width=2))
        
        return dwg.tostring()

    # 2. RENDER RESULTS
    st.subheader("📋 Professional Single Line Diagram")
    sld_svg = generate_sld()
    b64 = base64.b64encode(sld_svg.encode('utf-8')).decode('utf-8')
    st.markdown(f'<div style="background:#020617; padding:20px; border-radius:15px; border:1px solid #334155;"><img src="data:image/svg+xml;base64,{b64}" style="width:100%;"></div>', unsafe_allow_html=True)

    # 3. PDF BOM GENERATOR
    def generate_pdf_report():
        buffer = io.BytesIO()
        # Set margins for a professional look
        doc = SimpleDocTemplate(buffer, pagesize=A4, 
                                rightMargin=45, leftMargin=45, 
                                topMargin=45, bottomMargin=45)
        styles = getSampleStyleSheet()
        
        # Custom styles for more premium feel
        title_style = styles['Title']
        title_style.fontSize = 22
        title_style.textColor = colors.HexColor("#7c3aed")
        title_style.alignment = 1 # Center
        
        h2_style = styles['Heading2']
        h2_style.fontSize = 16
        h2_style.textColor = colors.HexColor("#4c1d95")
        h2_style.spaceBefore = 12
        h2_style.spaceAfter = 8
        
        normal_style = styles['Normal']
        normal_style.fontSize = 10
        normal_style.leading = 13
        normal_style.alignment = 4 # Justify

        story = []

        # --- PAGE 1: SYSTEM OVERVIEW & SLD ---
        story.append(Paragraph("Microgrid Panel Technical Report", title_style))
        story.append(Spacer(1, 15))
        
        story.append(Paragraph("1. System Overview", h2_style))
        description = f"""
        This report details the configuration and material requirements for a customized Microgrid Panel. 
        The system handles <b>{num_dg} DG(s)</b>, 
        {("<b>Grid supply</b> of " + str(grid_kw) + " kW,") if grid_kw > 0 else ""} 
        {("and <b>Solar PV</b> of " + str(solar_kw) + " kWp.") if solar_kw > 0 else ""}
        Managed via a centralized Microgrid Controller (MGC) for seamless power source management.
        """
        story.append(Paragraph(description, normal_style))
        story.append(Spacer(1, 15))
        
        story.append(Paragraph("2. Single Line Diagram (SLD)", h2_style))
        
        # Save SVG temporarily
        with open("temp_sld.svg", "w", encoding="utf-8") as f:
            f.write(sld_svg)

        # Convert SVG → drawing
        try:
            drawing = svg2rlg("temp_sld.svg")
            # Explicitly set the width and height we expect
            drawing.width = 1450
            drawing.height = 850
            
            # Calculate scale to fit width (A4 width - margins = 595 - 90 = 505)
            scaling_factor = 505.0 / 1450.0
            drawing.scale(scaling_factor, scaling_factor)
            
            # Update width/height after scaling so ReportLab positions subsequent elements correctly
            drawing.width = 1450 * scaling_factor
            drawing.height = 850 * scaling_factor
            
            # Center the drawing using a wrapper table
            sld_table = Table([[drawing]], colWidths=[505])
            sld_table.setStyle(TableStyle([('ALIGN', (0,0), (-1,-1), 'CENTER')]))
            story.append(sld_table)
        except Exception as e:
            story.append(Paragraph(f"[Error rendering SLD: {str(e)}]", normal_style))

        story.append(Spacer(1, 20))
        story.append(Paragraph("<i>Note: The diagram above illustrates the electrical topology and power flow between sources and outgoing feeders.</i>", normal_style))
        
        story.append(PageBreak())   
        
        # --- PAGE 2: BILL OF MATERIALS & SPECS ---
        story.append(Paragraph("3. Bill Of Material (BOM)", h2_style))
        story.append(Spacer(1, 8))
        
        table_data = [["Sr No", "Component / Description", "Rating", "Poles", "Qty"]]
        sr = 1
        if solar_kw > 0:
            table_data.append([sr, "Solar Incomer MCCB", f"{mccb_solar}A", f"{num_poles}P", "1"])
            sr+=1
        if grid_kw > 0:
            table_data.append([sr, "Grid Incomer MCCB", f"{mccb_grid}A", f"{num_poles}P", "1"])
            sr+=1
        for i, r in enumerate(dg_mccbs):
            table_data.append([sr, f"DG {i+1} Incomer MCCB", f"{r}A", f"{num_poles}P", "1"])
            sr+=1
        for i, r in enumerate(mccb_outputs):
            table_data.append([sr, f"Outgoing Feeder (O/G {i+1})", f"{r}A", f"{num_poles}P", "1"])
            sr+=1
        
        table_data.append([sr, f"{busbar_material} Main Busbar", f"{total_i:.1f}A Rated", "-", f"1 Set ({busbar_spec})"])
        sr += 1
        table_data.append([sr, "Microgrid Controller (MGC)", "Standard", "-", "1"])
        sr += 1
        
        # Adjusted colWidths to fit margins (505 total)
        table = Table(table_data, colWidths=[40, 200, 95, 70, 100])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#7c3aed")),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0,0), (-1,0), 10),
            ('BACKGROUND', (0,1), (-1,-1), colors.HexColor("#f8fafc")),
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
            ('FONTSIZE', (0,0), (-1,-1), 9),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.whitesmoke, colors.white])
        ]))
        story.append(table)
        
        story.append(Spacer(1, 25))
        story.append(Paragraph("4. Technical Highlights", h2_style))
        
        highlights = [
            f"<b>Total Busbar Current:</b> {total_i:.2f} A",
            f"<b>Required Busbar Area:</b> {busbar_area:.2f} mm²",
            f"<b>Recommended Busbar:</b> {busbar_spec}",
            f"<b>System:</b> {num_poles} Pole Configuration"
        ]
        
        for h in highlights:
            story.append(Paragraph(f"• {h}", normal_style))
            story.append(Spacer(1, 3))

        
        
        doc.build(story)
        buffer.seek(0)
        return buffer

    # 4. DOWNLOADS
    st.markdown('<div class="section-title">Export Documentation</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        st.download_button("📄 Download PDF BOM", data=generate_pdf_report(), file_name="Microgrid_Panel_BOM.pdf", mime="application/pdf")
    
else:
    st.info("👈 Use the designer panel on the left to configure your Microgrid and click 'Generate Final SLD & BOM'.")
    st.image("https://img.icons8.com/clouds/200/electricity.png")
