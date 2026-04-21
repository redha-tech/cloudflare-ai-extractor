import streamlit as st
import pandas as pd
import json
import base64
import io
import subprocess
import sys
import os

# --- 1. نظام الإصلاح التلقائي للمكتبات (Auto-Fix) ---
def ensure_dependencies():
    try:
        from mistralai import Mistral
    except (ImportError, ModuleNotFoundError):
        # محاولة التثبيت أو الترقية تلقائياً إذا فشل الاستيراد
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "mistralai"])
        st.rerun()

ensure_dependencies()
from mistralai import Mistral

# --- 2. إعدادات الصفحة وجلب المفاتيح ---
st.set_page_config(page_title="Mistral Vision Independent", layout="wide")

# جلب المفتاح من Secrets
MISTRAL_KEY = st.secrets.get("MISTRAL_API_KEY")

# --- 3. محرك Mistral Vision المطور ---
def process_with_mistral(file_bytes, mime_type):
    if not MISTRAL_KEY:
        st.error("🚨 Mistral API Key is missing in Secrets!")
        return None

    client = Mistral(api_key=MISTRAL_KEY)
    
    # تحويل الملف إلى Base64 ليفهمه محرك Vision
    base64_file = base64.b64encode(file_bytes).decode('utf-8')
    data_url = f"data:{mime_type};base64,{base64_file}"

    prompt = """
    Analyze this document image. Locate the table and extract all items.
    Required keys for each item: hs_code, description, qty, unit_price, amount, origin.
    Return ONLY a valid JSON object with a root key 'items'.
    Keep Arabic text as is in the description field.
    """

    try:
        # استخدام موديل pixtral المخصص للرؤية
        response = client.chat.complete(
            model="pixtral-12b-2409",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": data_url}
                    ]
                }
            ],
            response_format={"type": "json_object"}
        )
        
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        st.error(f"Mistral API Error: {str(e)}")
        return None

# --- 4. واجهة المستخدم الرسومية ---
st.title("🌪️ Clik-Plus | Mistral Pixtral Vision")
st.markdown("هذا الوضع يعمل بنظام **التصحيح الذاتي** للمكتبات.")

uploaded_file = st.file_uploader("ارفع صورة الفاتورة أو ملف (JPG/PNG)", type=['jpg', 'jpeg', 'png'])

if uploaded_file:
    # عرض الصورة لمعاينتها
    st.image(uploaded_file, caption="المستند الجاري تحليله", width=500)
    
    if st.button("🚀 تحليل باستخدام Mistral Vision", use_container_width=True, type="primary"):
        with st.spinner("المحرك الذكي يحلل الصورة الآن..."):
            file_bytes = uploaded_file.getvalue()
            mime_type = uploaded_file.type
            
            data = process_with_mistral(file_bytes, mime_type)
            
            if data and 'items' in data:
                df = pd.DataFrame(data['items'])
                st.success(f"تم استخراج {len(df)} صنف بنجاح!")
                st.dataframe(df, use_container_width=True)
                
                # إنشاء ملف Excel للتحميل
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df.to_excel(writer, index=False)
                
                st.download_button(
                    label="📥 تحميل النتائج كملف Excel",
                    data=output.getvalue(),
                    file_name=f"Mistral_Analysis_{uploaded_file.name}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
            else:
                st.error("❌ فشل في قراءة البيانات. تأكد من وضوح الصورة.")

st.divider()
st.caption("نظام Clik-Plus المطور | محرك التصحيح التلقائي V3.5")
