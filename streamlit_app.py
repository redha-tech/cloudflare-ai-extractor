import streamlit as st
import pandas as pd
import json
import base64
import io
import fitz  # PyMuPDF

# --- 1. الإعدادات ---
st.set_page_config(page_title="Clik-Plus | Smart OCR", layout="wide", page_icon="🚢")

MISTRAL_KEY = st.secrets.get("MISTRAL_API_KEY")
REQUIRED_COLS = ['hs_code', 'description', 'qty', 'unit_price', 'amount', 'origin', 'gross_weight', 'net_weight', 'pkg', 'invoice_number']

# --- 2. دالة تنظيف الجدول (حيوية لمنع الأخطاء) ---
def clean_and_total(df):
    # التأكد من وجود كل الأعمدة
    for col in REQUIRED_COLS:
        if col not in df.columns: df[col] = None
    
    # تحويل الأرقام
    num_cols = ['qty', 'unit_price', 'amount', 'gross_weight', 'net_weight']
    for col in num_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    # سطر المجموع
    totals = {col: 0 for col in num_cols}
    totals['description'] = '--- TOTAL ---'
    for col in num_cols: totals[col] = df[col].sum()
    
    df_total = pd.concat([df, pd.DataFrame([totals])], ignore_index=True)
    df_total = df_total[REQUIRED_COLS] # ترتيب الأعمدة
    df_total.index = list(range(1, len(df) + 1)) + ["TOTAL"]
    return df_total

# --- 3. دالة الذكاء الاصطناعي ---
def call_pixtral(file_bytes, mime_type):
    try:
        from mistralai import Mistral
        client = Mistral(api_key=MISTRAL_KEY)
        base64_file = base64.b64encode(file_bytes).decode('utf-8')
        data_url = f"data:{mime_type if 'pdf' not in mime_type else 'image/jpeg'};base64,{base64_file}"
        
        prompt = f"Extract items to JSON keys: {', '.join(REQUIRED_COLS)}. Keep Arabic. Return ONLY JSON key 'items'."
        
        response = client.chat.complete(
            model="pixtral-12b-2409",
            messages=[{"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": data_url}]}],
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        st.error(f"AI Error: {str(e)}")
        return None

# --- 4. الواجهة ---
st.title("🚢 Clik-Plus | المستخرج الذكي")
uploaded_file = st.file_uploader("ارفع الملف", type=['png', 'jpg', 'jpeg', 'pdf', 'xlsx', 'xls'])

if uploaded_file and st.button("🚀 تحليل واستخراج الآن"):
    with st.spinner("جاري المعالجة..."):
        df_result = pd.DataFrame()
        
        # حالة الإكسل: معالجة مباشرة لمنع الـ Timeout
        if uploaded_file.name.endswith(('xlsx', 'xls')):
            df_result = pd.read_excel(uploaded_file).ffill()
            # محاولة ذكية لمطابقة الأعمدة إذا كانت المسميات مختلفة
            df_result.columns = [col.lower().replace(" ", "_") for col in df_result.columns]
        
        # حالة الصور والـ PDF
        else:
            data = call_pixtral(uploaded_file.getvalue(), uploaded_file.type)
            if data and 'items' in data:
                df_result = pd.DataFrame(data['items'])

        if not df_result.empty:
            final_df = clean_and_total(df_result)
            
            # تنبيه الخصومات
            zeros = final_df[final_df['amount'] == 0].index.tolist()
            if zeros and "TOTAL" in zeros: zeros.remove("TOTAL")
            if zeros: st.warning(f"⚠️ أصناف صفرية في الأسطر: {', '.join(map(str, zeros))}")
            
            st.success("✅ تم الاستخراج بنجاح")
            st.dataframe(final_df, use_container_width=True)
            
            # التحميل
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                final_df.to_excel(writer, index=True)
            st.download_button("📥 تحميل Excel", output.getvalue(), "Result.xlsx")
        else:
            st.error("❌ تعذر استخراج البيانات. تأكد من محتوى الملف.")
