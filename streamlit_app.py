import streamlit as st
import pandas as pd
import json
import base64
import io
import re
import fitz  # PyMuPDF لملفات الـ PDF

# --- 1. إعدادات الصفحة ---
st.set_page_config(page_title="Clik-Plus | Smart Extractor", layout="wide", page_icon="🚢")

st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #FF4B4B; color: white; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

MISTRAL_KEY = st.secrets.get("MISTRAL_API_KEY")

# --- 2. وظائف المعالجة الذكية ---

def clean_dataframe(df):
    """توحيد الأعمدة ومنع التكرار وحساب الإجمالي بدقة"""
    mapping = {
        'hs_code': ['HS Code', 'hscode', 'hs code', 'تنسيق'],
        'description': ['Description', 'desc', 'items', 'item_description', 'الوصف'],
        'qty': ['Qty', 'quantity', 'الكمية'],
        'unit_price': ['Unit Price', 'price', 'Rate', 'السعر'],
        'amount': ['Amount', 'Total Amount', 'total', 'القيمة'],
        'origin': ['Origin', 'Country', 'المنشأ'],
        'weight': ['Weight', 'الوزن']
    }
    
    new_df = pd.DataFrame()
    for target, aliases in mapping.items():
        found = None
        for col in df.columns:
            if col.lower() == target or col.lower() in [a.lower() for a in aliases]:
                found = col
                break
        if found:
            new_df[target] = df[found]
        else:
            new_df[target] = 0 if target in ['qty', 'unit_price', 'amount'] else ""
    
    # تنظيف الأرقام (إزالة $ و * وغيرها) لضمان الجمع الصحيح
    for col in ['amount', 'unit_price', 'qty']:
        new_df[col] = new_df[col].astype(str).str.replace(r'[^\d.]', '', regex=True)
        new_df[col] = pd.to_numeric(new_df[col], errors='coerce').fillna(0)
        
    return new_df

# --- 3. دوال API ---

def call_mistral_vision(file_bytes, mime_type):
    """خاص بملفات PNG و JPG"""
    from mistralai import Mistral
    client = Mistral(api_key=MISTRAL_KEY)
    base64_file = base64.b64encode(file_bytes).decode('utf-8')
    
    prompt = "Extract items to JSON: hs_code, description, qty, unit_price, amount, origin, weight. Return ONLY JSON."
    
    response = client.chat.complete(
        model="pixtral-12b-2409",
        messages=[{"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": f"data:{mime_type};base64,{base64_file}"}
        ]}],
        response_format={"type": "json_object"}
    )
    return json.loads(response.choices[0].message.content)

def call_mistral_text(text_content):
    """خاص بملفات PDF القابلة للقراءة"""
    from mistralai import Mistral
    client = Mistral(api_key=MISTRAL_KEY)
    prompt = f"Convert this text to JSON items (hs_code, description, qty, unit_price, amount, origin, weight):\n{text_content}"
    
    response = client.chat.complete(
        model="mistral-small-latest",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )
    return json.loads(response.choices[0].message.content)

# --- 4. واجهة المستخدم ---
st.title("🚢 Clik-Plus | المستخرج الذكي")

uploaded_file = st.file_uploader("ارفع الملف (PDF, PNG, JPG, Excel)", type=['pdf', 'png', 'jpg', 'jpeg', 'xlsx', 'xls'])

if uploaded_file:
    file_ext = uploaded_file.name.split('.')[-1].lower()
    
    if st.button("🚀 استخراج البيانات الآن"):
        with st.spinner("جاري المعالجة..."):
            final_items = []

            # 1. معالجة PDF (نصي فقط كما طلبت)
            if file_ext == 'pdf':
                doc = fitz.open(stream=uploaded_file.getvalue(), filetype="pdf")
                full_text = "".join([page.get_text() for page in doc])
                doc.close()
                
                if full_text.strip():
                    data = call_mistral_text(full_text)
                    if data and 'items' in data: final_items = data['items']
                else:
                    st.error("⚠️ هذا الملف PDF لا يحتوي على نص قابل للقراءة.")

            # 2. معالجة الصور (PNG/JPG)
            elif file_ext in ['png', 'jpg', 'jpeg']:
                data = call_mistral_vision(uploaded_file.getvalue(), uploaded_file.type)
                if data and 'items' in data: final_items = data['items']

            # 3. معالجة Excel
            elif file_ext in ['xlsx', 'xls']:
                df_excel = pd.read_excel(uploaded_file)
                final_items = df_excel.to_dict(orient='records')

            # --- عرض النتائج ---
            if final_items:
                df = clean_dataframe(pd.DataFrame(final_items))
                df.index = df.index + 1
                df.index.name = "#"

                # تنبيه القيم الصفرية في سطر واحد
                zero_indices = df[df['amount'] <= 0].index.tolist()
                if zero_indices:
                    st.warning(f"⚠️ تنبيه: قيم صفرية في الأصناف: {', '.join([f'#{i}' for i in zero_indices])}")

                total_sum = df['amount'].sum()
                st.success(f"✅ تم استخراج {len(df)} صنف!")
                st.dataframe(df, use_container_width=True)
                st.info(f"📊 **إجمالي المبلغ الكلي: {total_sum:,.2f}**")
                
                # تحميل Excel
                output = io.BytesIO()
                df_exp = df.copy()
                df_exp.loc['Total'] = None
                df_exp.at['Total', 'amount'] = total_sum
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df_exp.to_excel(writer, index=True)
                st.download_button("📥 تحميل ملف Excel", output.getvalue(), f"Extracted_{uploaded_file.name}.xlsx")
            else:
                st.error("⚠️ لم يتم العثور على بيانات.")
