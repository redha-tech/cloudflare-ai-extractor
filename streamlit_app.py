import streamlit as st
import pandas as pd
import json
import base64
import io
import importlib

# --- 1. إعدادات الصفحة ---
st.set_page_config(page_title="Clik-Plus Official", layout="wide")

MISTRAL_KEY = st.secrets.get("MISTRAL_API_KEY")

# --- 2. دالة المعالجة الحديثة ---
def process_with_mistral(file_bytes, mime_type):
    try:
        # استيراد المكتبة بالطريقة الحديثة فقط
        from mistralai import Mistral
        client = Mistral(api_key=MISTRAL_KEY)
    except Exception as e:
        st.error(f"مشكلة في مكتبة Mistral: {str(e)}")
        return None

    # تحويل الملف لـ Base64
    base64_file = base64.b64encode(file_bytes).decode('utf-8')
    data_url = f"data:{mime_type};base64,{base64_file}"

    prompt = (
        "Extract all items into JSON format: hs_code, description, qty, unit_price, amount, origin. "
        "Maintain Arabic text. Return ONLY JSON with an 'items' key."
    )

    try:
        # تنفيذ الطلب باستخدام الطريقة الحديثة للـ SDK
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
        st.error(f"خطأ أثناء التحليل: {str(e)}")
        return None

# --- 3. واجهة المستخدم ---
st.title("🚢 Clik-Plus | المستخرج الذكي")
st.markdown("يدعم الفواتير بصيغة PDF و الصور (Pixtral Engine)")

uploaded_file = st.file_uploader("ارفع الفاتورة (PDF أو صورة)", type=['pdf', 'jpg', 'png', 'jpeg'])

if uploaded_file:
    if st.button("🚀 تحليل واستخراج البيانات الآن", use_container_width=True, type="primary"):
        with st.spinner("جاري استخراج البيانات من المستند..."):
            data = process_with_mistral(uploaded_file.getvalue(), uploaded_file.type)
            
            if data and 'items' in data:
                df = pd.DataFrame(data['items'])
                st.success(f"✅ تم استخراج {len(df)} صنف بنجاح!")
                st.dataframe(df, use_container_width=True)
                
                # إنشاء ملف الإكسل
                buf = io.BytesIO()
                with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
                    df.to_excel(writer, index=False)
                
                st.download_button(
                    label="📥 تحميل النتائج كملف Excel",
                    data=buf.getvalue(),
                    file_name=f"Extracted_Data_{uploaded_file.name}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
            else:
                st.error("❌ لم يتم العثور على بيانات منظمة. جرب صورة أوضح.")
