import streamlit as st
import pandas as pd
import requests
import json
import re
import io
import docx
import pdfplumber

# --- 1. إعدادات الصفحة وجلب المفاتيح ---
st.set_page_config(page_title="Clik-Plus Universal Extractor", layout="wide")

CF_ID = st.secrets.get("CF_ACCOUNT_ID")
CF_TOKEN = st.secrets.get("CF_AUTH_TOKEN")

# --- 2. دوال معالجة أنواع الملفات المختلفة ---

def extract_text_from_pdf(file):
    with pdfplumber.open(file) as pdf:
        return "\n".join([page.extract_text() or "" for page in pdf.pages])

def extract_text_from_docx(file):
    doc = docx.Document(file)
    return "\n".join([para.text for para in doc.paragraphs])

def extract_json_safely(text):
    try:
        match = re.search(r'\{.*\}', text, re.DOTALL)
        return json.loads(match.group()) if match else None
    except:
        return None

# --- 3. محرك Cloudflare AI ---
def process_with_cloudflare(text):
    if not CF_ID or not CF_TOKEN:
        st.error("🚨 Cloudflare Credentials Missing!")
        return None

    url = f"https://api.cloudflare.com/client/v4/accounts/{CF_ID}/ai/run/@cf/meta/llama-3-8b-instruct"
    headers = {"Authorization": f"Bearer {CF_TOKEN}"}
    
    payload = {
        "messages": [
            {
                "role": "system", 
                "content": "You are a professional customs data extractor. Return JSON ONLY. Format: {'items': [{'hs_code': '...', 'description': '...', 'qty': 0, 'unit_price': 0, 'amount': 0, 'origin': '...'}]}"
            },
            {"role": "user", "content": f"Extract the table data from this text into JSON:\n\n{text[:4000]}"} # نرسل أول 4000 حرف لضمان السرعة
        ]
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        if response.status_code != 200:
            st.error(f"Cloudflare Error {response.status_code}: {response.text}")
            return None
            
        result = response.json()
        if result.get("success"):
            return extract_json_safely(result["result"]["response"])
        return None
    except Exception as e:
        st.error(f"Connection Error: {e}")
        return None

# --- 4. واجهة المستخدم الرسومية ---
st.title("🚢 Clik-Plus | Universal AI Extractor")
st.markdown("يدعم الملفات: **PDF, Word, Excel, CSV, Text**")

uploaded_file = st.file_uploader("ارفع ملفك هنا", type=['pdf', 'docx', 'xlsx', 'xls', 'csv', 'txt'])

if uploaded_file:
    ext = uploaded_file.name.split('.')[-1].lower()
    text_content = ""

    try:
        # معالجة ملفات Excel و CSV
        if ext in ['xlsx', 'xls']:
            text_content = pd.read_excel(uploaded_file).to_csv(index=False)
        elif ext == 'csv':
            text_content = pd.read_csv(uploaded_file).to_csv(index=False)
        # معالجة ملفات PDF
        elif ext == 'pdf':
            text_content = extract_text_from_pdf(uploaded_file)
        # معالجة ملفات Word
        elif ext == 'docx':
            text_content = extract_text_from_docx(uploaded_file)
        # معالجة ملفات النص
        else:
            text_content = uploaded_file.read().decode("utf-8")

        if st.button("🚀 ابدأ تحليل الملف الآن", use_container_width=True, type="primary"):
            if not text_content.strip():
                st.warning("⚠️ الملف فارغ أو لا يمكن قراءة النص منه.")
            else:
                with st.spinner("جاري المعالجة عبر Cloudflare AI..."):
                    data = process_with_cloudflare(text_content)
                    
                    if data and 'items' in data:
                        df_final = pd.DataFrame(data['items'])
                        st.success(f"تم استخراج {len(df_final)} صنف بنجاح!")
                        st.dataframe(df_final, use_container_width=True)
                        
                        # تصدير إكسل
                        buf = io.BytesIO()
                        with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
                            df_final.to_excel(writer, index=False)
                        
                        st.download_button(
                            "📥 تحميل النتائج كملف Excel",
                            buf.getvalue(),
                            f"extracted_{uploaded_file.name}.xlsx",
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True
                        )
                    else:
                        st.error("❌ فشل الاستخراج. تأكد من جودة الملف أو صلاحيات التوكن.")
    except Exception as e:
        st.error(f"حدث خطأ أثناء قراءة الملف: {e}")

st.markdown("---")
st.caption("نظام Clik-Plus المطور | يعمل بمحرك Cloudflare Llama 3")
