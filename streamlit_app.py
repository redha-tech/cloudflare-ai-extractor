import streamlit as st
import pandas as pd
import json
import base64
import io
import fitz  # PyMuPDF

# --- 1. آلية الاستيراد المرنة ---
try:
    from mistralai import Mistral
except ImportError:
    try:
        from mistralai.client import Mistral
    except ImportError:
        st.error("❌ السيرفر لا يزال لا يرى مكتبة Mistral. يرجى الضغط على Manage App ثم Reboot App.")
        st.stop()

# --- 2. إعدادات الصفحة والواجهة ---
st.set_page_config(page_title="Clik-Plus | Smart OCR", layout="wide", page_icon="🚢")

st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #FF4B4B; color: white; }
    .stDataFrame { border: 1px solid #e6e9ef; border-radius: 5px; }
    </style>
    """, unsafe_allow_html=True)

MISTRAL_KEY = st.secrets.get("MISTRAL_API_KEY")

# --- 3. دالات المعالجة الذكية ---

# --- تحديث دالة البرومبت لتصبح "عالمية" وتفهم أي فاتورة ---

def get_smart_prompt(context_type="image", text_content=None):
    base_prompt = (
        "You are an AI Data Scientist specialized in Global Trade Documents. "
        "Your goal is to find the 'Logic' of the invoice, regardless of its layout:\n"
        
        "1. **Semantic Mapping**: Even if headers are missing, identify columns by content:\n"
        "   - **HS_CODE**: Look for numbers that are 6, 8, or 10 digits long. "
        "     (Logic: HS codes often have dots like 7326.90. Ignore 13-digit barcodes).\n"
        "   - **DESCRIPTION**: The longest text field in the row.\n"
        "   - **QTY**: Small integers near the description.\n"
        "   - **PRICE**: Numbers with decimals (0.00).\n"
        "   - **ORIGIN**: Look for country names (China, USA, etc.) or 'C/O'.\n"
        
        "2. **Table Reconstruction**: If the invoice has multiple rows, ensure every item is captured. "
        "Do not skip rows. If a value is missing in one row but exists in the header, use logic.\n"
        
        "3. **Zero Translation**: Extract text EXACTLY. If the description is in Arabic, keep it Arabic. "
        "If it's English, keep it English.\n"
        
        "4. **Strict JSON**: Return ONLY a valid JSON object with the key 'items'."
    )
    if context_type == "text":
        return f"{base_prompt}\n\nInvoice Content to Analyze:\n{text_content}"
    return base_prompt

# --- تحديث منطق الإكسل ليكون مرناً جداً (Extreme Flexibility) ---
smart_map = {
    'hs_code': ['hs', 'code', 'commodity', 'tariff', 'tariff', 'h.s', 'بند', 'نسق', 'جمارك'],
    'description': ['desc', 'item', 'product', 'article', 'البيان', 'الوصف', 'الصنف', 'السلعة'],
    'qty': ['qty', 'quantity', 'qnt', 'count', 'الكمية', 'عدد', 'العدد'],
    'unit_price': ['price', 'rate', 'unit', 'fob', 'سعر', 'فئة', 'قيمة'],
    'amount': ['amount', 'total', 'ext', 'value', 'المبلغ', 'الاجمالي', 'القيمة'],
    'origin': ['origin', 'c/o', 'made', 'source', 'المنشأ', 'بلد', 'مصدر']
}   
                new_cols = {}
                for official, synonyms in smart_map.items():
                    for actual in df_raw.columns:
                        if any(syn.lower() in actual.lower() for syn in synonyms):
                            new_cols[actual] = official
                            break
                
                df_raw = df_raw.rename(columns=new_cols)
                required = ['hs_code', 'description', 'qty', 'unit_price', 'amount', 'origin']
                for col in required:
                    if col not in df_raw.columns: df_raw[col] = ""
                
                final_items = df_raw[required].to_dict(orient='records')

            else:
                data = process_with_pixtral(uploaded_file.getvalue(), uploaded_file.type)
                if data and 'items' in data: final_items = data['items']

            # --- عرض النتائج المشتركة وتنسيقها ---
            if final_items:
                df = pd.DataFrame(final_items)
                
                # تنظيف الأرقام
                for col in ['qty', 'amount']:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

                # إضافة الصفوف الفارغة والإجمالي
                empty_data = {col: [""] * 2 for col in df.columns}
                df_empty = pd.DataFrame(empty_data)

                totals = {col: "" for col in df.columns}
                totals['description'] = "TOTAL / الإجمالي"
                totals['qty'] = df['qty'].sum()
                totals['amount'] = df['amount'].sum()
                df_total = pd.DataFrame([totals])

                df_final = pd.concat([df.astype(object), df_empty, df_total], ignore_index=True)
                
                new_idx = list(range(1, len(df) + 1)) + [" ", "  ", "TOTAL"]
                df_final.index = new_idx

                st.success(f"✅ تم تحليل {len(df)} صنف بذكاء!")
                
                def highlight(s):
                    return ['background-color: #ffffcc; font-weight: bold' if s.name == "TOTAL" else '' for _ in s]

                st.dataframe(df_final.style.apply(highlight, axis=1), use_container_width=True)
                
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df_final.to_excel(writer, index=True, sheet_name='ExtractedData')
                    worksheet = writer.sheets['ExtractedData']
                    total_fmt = writer.book.add_format({'bg_color': '#ffffcc', 'bold': True, 'border': 1})
                    worksheet.set_row(len(df_final), None, total_fmt)
                
                st.download_button("📥 تحميل النتائج كملف Excel", output.getvalue(), f"Extracted_{uploaded_file.name}.xlsx")
            else:
                st.warning("⚠️ لم يتم العثور على بيانات، يرجى التأكد من جودة المستند.")
