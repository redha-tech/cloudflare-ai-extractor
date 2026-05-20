import streamlit as st
import pandas as pd
import io
import datetime
from ai_engine import smart_route_file, clean_numeric_string, apply_weight_distribution

# 1. إعداد الصفحة والتنسيق البصري الحديث (Modern CSS)
st.set_page_config(layout="wide", page_title="Clik-Plus Intelligent Extraction")

st.markdown("""
    <style>
    /* خلفية التطبيق */
    .stApp { background-color: #f8fafc; }
    
    /* تصميم بطاقات الملفات */
    .file-card {
        background-color: white;
        padding: 20px;
        border-radius: 12px;
        border: 1px solid #e2e8f0;
        margin-bottom: 15px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    
    /* زر المعالجة الرئيسي */
    .stButton>button[kind="primary"] {
        background: linear-gradient(90deg, #1e293b 0%, #334155 100%);
        border: none;
        padding: 12px;
        font-weight: bold;
        letter-spacing: 0.5px;
    }
    
    /* تنسيق العناوين */
    h1 { color: #0f172a; font-weight: 800 !important; }
    .stMetric { background: white; padding: 15px; border-radius: 10px; border: 1px solid #e2e8f0; }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. إدارة الجلسة والدخول
# ==========================================
for key in ['logged_in', 'ai_total_val', 'ai_discount_val', 'uploader_key']:
    if key not in st.session_state:
        st.session_state[key] = False if key == 'logged_in' else 0.0

if 'data_store' not in st.session_state:
    st.session_state.data_store = pd.DataFrame()

# دالة التنسيق البصري للجدول
def style_dataframe(df):
    def apply_styles(row):
        styles = [''] * len(row)
        if row.name == 'TOTAL':
            return ['background-color: #f1f5f9; font-weight: bold; color: #0f172a'] * len(row)
        for i, col_name in enumerate(row.index):
            if col_name in ["qty", "amount", "gross_weight"] and clean_numeric_string(row[col_name]) == 0:
                styles[i] = 'background-color: #fee2e2; color: #991b1b;'
        return styles
    return df.style.apply(apply_styles, axis=1).format(
        subset=["amount", "gross_weight", "net_weight", "unit_price"], formatter="{:.3f}"
    )

# واجهة تسجيل الدخول (Modern Login)
if not st.session_state.logged_in:
    col_l, col_m, col_r = st.columns([1, 2, 1])
    with col_m:
        st.markdown("<div style='height: 100px;'></div>", unsafe_allow_html=True)
        with st.container():
            st.title("🔐 Access Portal")
            u = st.text_input("Username")
            p = st.text_input("Password", type="password")
            if st.button("Sign In", use_container_width=True, type="primary"):
                if u == st.secrets["USER_NAME"] and p == st.secrets["USER_PASS"]:
                    st.session_state.logged_in = True
                    st.rerun()
                else:
                    st.error("Invalid credentials")
    st.stop()

# ==========================================
# 3. لوحة التحكم الرئيسية
# ==========================================
st.markdown("<h1>🚢 Clik-Plus <span style='color: #3b82f6;'>Intelligent Extraction</span></h1>", unsafe_allow_html=True)

# عرض ملخص الحالة المحاسبية
if not st.session_state.data_store.empty:
    with st.container():
        df_chk = st.session_state.data_store
        curr_sum = df_chk["amount"].sum()
        target_sum = st.session_state.ai_total_val
        diff = abs(curr_sum - target_sum)
        
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("إجمالي الجدول", f"{curr_sum:,.3f}")
        m2.metric("إجمالي الفاتورة", f"{target_sum:,.3f}")
        m3.metric("الخصم المستخرج", f"{st.session_state.ai_discount_val:,.3f}")
        m4.metric("الأصناف", len(df_chk))
        
        if diff > 0.1:
            st.warning(f"⚠️ يوجد فرق مالي قدره {diff:,.3f}")
        
        if st.button("🛠️ إصلاح مالي تلقائي", use_container_width=True):
            st.session_state.data_store["amount"] = (st.session_state.data_store["qty"] * st.session_state.data_store["unit_price"]).round(3)
            st.session_state.ai_discount_val = 0.0
            st.success("تمت إعادة الحساب!")
            st.rerun()

st.write("##")

# رفع الملفات (Modern Uploader)
uploaded_files = st.file_uploader(
    "اسحب الملفات هنا", 
    accept_multiple_files=True, 
    key=f"up_{st.session_state.uploader_key}",
    label_visibility="collapsed"
)

sheet_selection = {}
model_preferences = {}

if uploaded_files:
    st.markdown("### ⚙️ Configure Extraction")
    for f in uploaded_files:
        with st.container():
            st.markdown(f"""
            <div class="file-card">
                <div style="display: flex; justify-content: space-between;">
                    <span style="font-weight: bold; color: #1e293b;">📄 {f.name}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            c1, c2 = st.columns([2, 3])
            with c1:
                model_preferences[f.name] = st.radio(
                    "Select Engine:", 
                    ["Auto (Smart)", "Gemini", "Groq"], 
                    key=f"mod_{f.name}", 
                    horizontal=True
                )
            with c2:
                if f.name.endswith(('.xlsx', '.xls')):
                    xl = pd.ExcelFile(f)
                    sheet_selection[f.name] = st.multiselect(
                        "Select Sheets:", xl.sheet_names, 
                        default=[xl.sheet_names[0]], key=f"sh_{f.name}"
                    )
                else:
                    st.markdown("<p style='padding-top: 30px; color: #64748b;'>Full document will be analyzed</p>", unsafe_allow_html=True)
        st.write("")

    if st.button("🚀 Start Intelligent Analysis", use_container_width=True, type="primary"):
        all_results = []
        total_ai, disc_ai = 0.0, 0.0
        cols = ["hs_code", "description", "qty", "unit_price", "amount", "origin", "gross_weight", "net_weight", "Pkg"]
        prompt = f"Extract items into JSON. Keys: {cols}. Include 'invoice_grand_total' and 'discount_amount' as root keys."

        for f in uploaded_files:
            with st.spinner(f"Processing {f.name}..."):
                selected_model = model_preferences.get(f.name, "Auto (Smart)")
                data, engine = smart_route_file(f, sheet_selection, prompt, user_model=selected_model)
                if data and 'items' in data:
                    total_ai += clean_numeric_string(data.get("invoice_grand_total", 0))
                    disc_ai += clean_numeric_string(data.get("discount_amount", 0))
                    for i in data['items']:
                        i['invoice_number'] = f.name
                    all_results.extend(data['items'])
        
        if all_results:
            st.session_state.data_store = apply_weight_distribution(pd.DataFrame(all_results))
            st.session_state.ai_total_val = total_ai
            st.session_state.ai_discount_val = disc_ai
            st.rerun()

# ==========================================
# 4. عرض النتائج والتحميل
# ==========================================
if not st.session_state.data_store.empty:
    st.divider()
    main_df = st.session_state.data_store.copy()
    main_df.index = range(1, len(main_df) + 1)
    
    totals = {
        "description": "--- TOTAL ---", 
        "qty": int(main_df["qty"].sum()), 
        "amount": round(main_df["amount"].sum(), 3), 
        "gross_weight": round(main_df["gross_weight"].sum(), 3), 
        "net_weight": round(main_df["net_weight"].sum(), 3)
    }
    display_df = pd.concat([main_df, pd.DataFrame([totals], index=["TOTAL"])])
    
    st.subheader("📊 Extraction Results")
    st.dataframe(style_dataframe(display_df), use_container_width=True, height=500)
    
    c_dl, c_clr = st.columns([4, 1])
    with c_dl:
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
            main_df.to_excel(writer, index=False)
        st.download_button(
            "📥 Download Professional Excel Report", 
            buf.getvalue(), 
            f"Extraction_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
            use_container_width=True
        )
    with c_clr:
        if st.button("🗑️ Clear Session", use_container_width=True):
            st.session_state.data_store = pd.DataFrame()
            st.session_state.uploader_key += 1
            st.rerun()
