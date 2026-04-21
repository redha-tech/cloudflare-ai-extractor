import streamlit as st
import pandas as pd
import anthropic
import json
import re
import io
import docx
import pdfplumber

# --- 1. إعداد الصفحة وجلب المفاتيح بنظام UTF-8 ---
st.set_page_config(page_title="Clik-Plus Claude Vision", layout="wide")

# جلب مفتاح Anthropic من الـ Secrets
CLAUDE_KEY = st.secrets.get("ANTHROPIC_API_KEY")

# --- 2. دوال معالجة الملفات مع دعم اللغة العربية ---

def extract_text_from_pdf(file):
    try:
        with pdfplumber.open(file) as pdf:
            # استخراج النص مع الحفاظ على ترتيب الأسطر لدعم الجداول
            return "\n".join([page.extract_text() or "" for page in pdf.pages])
    except Exception as e:
        return f"Error reading PDF: {str(e)}"

def extract_text_from_docx(file):
    try:
        doc = docx.Document(file)
        return "\n".join([para.text for para in doc.paragraphs])
    except Exception as e:
        return f"Error reading DOCX: {str(e)}"

def extract_json_safely(text):
    try:
        # البحث عن كود الـ JSON داخل رد المحرك
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            clean_json = match.group()
            return json.loads(clean_json)
        return None
    except Exception as e:
        st.error(f"JSON Parsing Error: {e}")
        return None

# --- 3. محرك الاستخراج الذكي (Claude 3.5 Sonnet) ---
def process_with_claude(text):
    if not CLAUDE_KEY:
        st.error("🚨 Anthropic API Key is missing in Streamlit Secrets!")
        return None

    client = anthropic.Anthropic(api_key=CLAUDE_KEY)
    
    # حل مشكلة ASCII: تنظيف النص وتجهيزه بتشفير UTF-8
    try:
        safe_text = text.encode('utf-8', errors='ignore').decode('utf-8')
    except:
        safe_text = text

    system_instr = (
        "You are an expert in customs logistics and international trade. "
        "Your task is to extract product items from the provided document text. "
        "Extract these fields: hs_code, description, qty, unit_price, amount, origin. "
        "The text contains Arabic and English; preserve Arabic text in the 'description' and 'origin' fields. "
        "Return ONLY a valid JSON object with the key 'items'."
    )
    
    try:
        # إرسال البيانات لـ Claude
        message = client.messages.create(
            model="claude-3-5-sonnet-20240620",
            max_tokens=4096,
            system=system_instr,
            messages=[
                {"role": "user", "content": f"Extract the table items from this document text:\n\n{safe_text}"}
            ]
        )
        
        return extract_json_safely(message.content[0].text)
    except Exception as e:
        st.error(f"Claude API Error: {str(e)}")
        return None

# --- 4. واجهة المستخدم (UI) ---
st.title("🚢 Clik-Plus | Claude 3.5 Vision Extractor")
st.markdown("المحرك الثالث: يدعم استخراج البيانات المعقدة باللغة العربية والإنجليزية")

uploaded_file = st.file_uploader("ارفع ملف الفاتورة أو الـ CRO (PDF, Excel, Word, Text)", 
                                 type=['pdf', 'docx', 'xlsx', 'xls', 'csv', 'txt'])

if uploaded_file:
    ext = uploaded_file.name.split('.')[-1].lower()
    text_content = ""

    with st.spinner("جاري قراءة الملف..."):
        try:
            if ext in ['xlsx', 'xls']:
                text_content = pd.read_excel(uploaded_file).to_csv(index=False)
            elif ext == 'csv':
                text_content = pd.read_csv(uploaded_file).to_csv(index=False)
            elif ext == 'pdf':
                text_content = extract_text_from_pdf(uploaded_file)
            elif ext == 'docx':
                text_content = extract_text_from_docx(uploaded_file)
            else:
                text_content = uploaded_file.read().decode("utf-8", errors='ignore')
        except Exception as e:
            st.error(f"خطأ في قراءة الملف: {e}")

    if st.button("🚀 ابدأ التحليل الاحترافي", use_container_width=True, type="primary"):
        if not text_content.strip():
            st.warning("⚠️ الملف فارغ أو تعذر استخراج النص منه.")
        else:
            with st.spinner("Claude 3.5 يقوم بتحليل الجداول الآن..."):
                data = process_with_claude(text_content)
                
                if data and 'items' in data:
                    df_final = pd.DataFrame(data['items'])
                    st.success(f"✅ تم استخراج {len(df_final)} صنف بنجاح")
                    
                    # عرض الجدول
                    st.dataframe(df_final, use_container_width=True)
                    
                    # إنشاء ملف إكسل للتحميل
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                        df_final.to_excel(writer, index=False)
                    
                    st.download_button(
                        label="📥 تحميل النتائج (Excel)",
                        data=output.getvalue(),
                        file_name=f"Extracted_{uploaded_file.name}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )
                else:
                    st.error("❌ فشل المحرك في تنظيم البيانات. يرجى التأكد من وضوح الملف.")

st.divider()
st.caption("Powered by Anthropic Claude 3.5 Sonnet | Clik-Plus v3.0")
