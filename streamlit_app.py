import streamlit as st
import pandas as pd
import json
import base64
import io

# --- 1. محاولة الاستيراد مع معالجة الخطأ بشكل صريح ---
try:
    from mistralai import Mistral
except Exception:
    try:
        from mistralai.client import MistralClient as Mistral
    except Exception:
        st.error("🚨 مكتبة Mistral غير مثبتة. تأكد من وجود 'mistralai' في requirements.txt وعمل Reboot للتطبيق.")
        st.stop() # إيقاف التطبيق هنا لمنع ظهور NameError لاحقاً

# --- 2. إعدادات الصفحة ---
st.set_page_config(page_title="Mistral Vision Pro", layout="wide")

MISTRAL_KEY = st.secrets.get("MISTRAL_API_KEY")

# --- 3. دالة المعالجة ---
def process_with_mistral(file_bytes, mime_type):
    if not MISTRAL_KEY:
        st.error("🚨 المفتاح MISTRAL_API_KEY مفقود من Secrets!")
        return None

    # تهيئة العميل
    client = Mistral(api_key=MISTRAL_KEY)

    # تحويل الملف إلى Base64
    base64_file = base64.b64encode(file_bytes).decode('utf-8')
    data_url = f"data:{mime_type};base64,{base64_file}"

    prompt = (
        "You are an expert customs data extractor. Analyze this document (PDF or Image). "
        "Extract all items into a JSON format with these exact keys: "
        "hs_code, description, qty, unit_price, amount, origin. "
        "Maintain Arabic text for descriptions. Return ONLY the JSON object with the key 'items'."
    )

    try:
        # استخدام الموديل Pixtral الذي يدعم الصور والمستندات
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
        
        content = response.choices[0].message.content
        return json.loads(content)
    except Exception as e:
        st.error(f"Mistral API Error: {str(e)}")
        return None

# --- 4. واجهة المستخدم ---
st.title("🌪️ Mistral Vision | Multi-Format Extractor")
st.markdown("دعم كامل لملفات الفواتير بصيغة PDF و الصور.")

uploaded_file = st.file_uploader("ارفع المستند (PDF, JPG, PNG)", type=['pdf', 'jpg', 'jpeg', 'png'])

if uploaded_file:
    if uploaded_file.type == "application/pdf":
        st.info(f"📄 تم تحميل ملف PDF: {uploaded_file.name}")
    else:
        st.image(uploaded_file, width=300)

    if st.button("🚀 ابدأ التحليل الاستخراجي", use_container_width=True, type="primary"):
        with st.spinner("جاري معالجة المستند واستخراج الجداول..."):
            data = process_with_mistral(uploaded_file.getvalue(), uploaded_file.type)
            
            if data and 'items' in data:
                df = pd.DataFrame(data['items'])
                st.success("✅ اكتمل الاستخراج!")
                st.dataframe(df, use_container_width=True)
                
                # إنشاء ملف الإكسل
                buf = io.BytesIO()
                with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
                    df.to_excel(writer, index=False)
                
                st.download_button(
                    label="📥 تحميل النتائج (Excel)",
                    data=buf.getvalue(),
                    file_name=f"Extracted_{uploaded_file.name}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
