import streamlit as st
import pandas as pd
import anthropic
import json
import re
import io
import docx
import pdfplumber

# --- 1. إعدادات الصفحة وجلب المفاتيح ---
st.set_page_config(page_title="Clik-Plus Claude Extractor", layout="wide")

# جلب مفتاح Anthropic من الـ Secrets
CLAUDE_KEY = st.secrets.get("ANTHROPIC_API_KEY")

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

# --- 3. محرك Anthropic Claude 3.5 Sonnet ---
def process_with_claude(text):
    if not CLAUDE_KEY:
        st.error("🚨 Anthropic API Key Missing in Secrets!")
        return None

    client = anthropic.Anthropic(api_key=CLAUDE_KEY)
    
    # البرومبت المخصص لاستخراج بيانات الجمارك
    system_prompt = (
        "You are a professional customs documentation expert. "
        "Your task is to extract item data into a strict JSON format. "
        "Fields: hs_code, description, qty, unit_price, amount, origin. "
        "Return ONLY the JSON object."
    )
    
    try:
        message = client.messages.create(
            model="claude-3-5-sonnet-20240620",
            max_tokens=4096,
            system=system_prompt,
            messages=[
                {"role": "user", "content": f"Extract the table data from this document text:\n\n{text}"}
            ]
        )
        
        # استلام النص من Claude
        response_text = message.content[0].text
        return extract_json_safely(response_text)
    except Exception as e:
        st.error(f"Claude API Error: {e}")
        return None

# --- 4. واجهة المستخدم الرسومية ---
st.title("🚢 Clik-Plus | Claude 3.5 Intelligent Extractor")
st.markdown("المستخرج الاحترافي يدعم: **PDF, Word, Excel, CSV, Text**")

uploaded_file = st.file_uploader("ارفع ملفك هنا", type=['pdf', 'docx', 'xlsx', 'xls', 'csv', 'txt'])

if uploaded_file:
    ext = uploaded_file.name.split('.')[-1].lower()
    text_content = ""

    try:
        with st.spinner("جاري قراءة وتحويل الملف..."):
            if ext in ['xlsx', 'xls']:
                text_content = pd.read_excel(uploaded_file).to_csv(index=False)
            elif ext == 'csv':
                text_content = pd.read_csv(uploaded_file).to_csv(index=False)
            elif ext == 'pdf':
                text_content = extract_text_from_pdf(uploaded_file)
            elif ext == 'docx':
                text_content = extract_text_from_docx(uploaded_file)
            else:
                text_content = uploaded_file.read().decode("utf-8")

        if st.button("🚀 تحليل باستخدام Claude 3.5 Sonnet", use_container_width=True, type="primary"):
            if not text_content.strip():
                st.warning("⚠️ الملف فارغ أو لا يحتوي على نص قابل للقراءة.")
            else:
                with st.spinner("Claude يقوم بتحليل البيانات الآن..."):
                    data = process_with_claude(text_content)
                    
                    if data and 'items' in data:
                        df_final = pd.DataFrame(data['items'])
                        st.success(f"✅ تم استخراج {len(df_final)} صنف بدقة!")
                        st.dataframe(df_final, use_container_width=True)
                        
                        # تصدير إكسل
                        buf = io.BytesIO()
                        with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
                            df_final.to_excel(writer, index=False)
                        
                        st.download_button(
                            "📥 تحميل النتائج كملف Excel",
                            buf.getvalue(),
                            f"Claude_Extracted_{uploaded_file.name}.xlsx",
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True
                        )
                    else:
                        st.error("❌ فشل Claude في تحليل البيانات. تأكد من وضوح الملف أو صلاحية المفتاح.")
    except Exception as e:
        st.error(f"حدث خطأ أثناء معالجة الملف: {e}")

st.markdown("---")
st.caption("نظام Clik-Plus | مدعوم بمحرك Anthropic Claude 3.5 Sonnet")
