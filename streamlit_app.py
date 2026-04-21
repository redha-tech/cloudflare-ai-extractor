import streamlit as st
import pandas as pd
import json
import base64
import io

# --- 1. آلية الاستيراد المرنة (تجنب ImportError) ---
try:
    # الطريقة للنسخة الحديثة v1.1.0 وما فوق
    from mistralai import Mistral
except ImportError:
    try:
        # خطة بديلة لبعض بيئات التشغيل التي قد تجلب نسخة v2.0
        from mistralai.client import Mistral
    except ImportError:
        st.error("❌ السيرفر لا يزال لا يرى مكتبة Mistral. يرجى الضغط على Manage App ثم Reboot App.")
        st.stop()

# --- 2. إعدادات الصفحة والواجهة ---
st.set_page_config(page_title="Clik-Plus | Smart OCR", layout="wide", page_icon="🚢")

# تنسيق CSS بسيط لتحسين المظهر
st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #FF4B4B; color: white; }
    .stDataFrame { border: 1px solid #e6e9ef; border-radius: 5px; }
    </style>
    """, unsafe_allow_html=True)

# جلب المفتاح من Secrets
MISTRAL_KEY = st.secrets.get("MISTRAL_API_KEY")

# --- 3. دالة معالجة البيانات ---
def process_with_pixtral(file_bytes, mime_type):
    if not MISTRAL_KEY:
        st.error("⚠️ مفتاح API مفقود! أضف MISTRAL_API_KEY في إعدادات Secrets.")
        return None

    try:
        # إنشاء العميل
        client = Mistral(api_key=MISTRAL_KEY)
        
        # تحويل الملف إلى Base64 ليتناسب مع Pixtral Engine
        base64_file = base64.b64encode(file_bytes).decode('utf-8')
        data_url = f"data:{mime_type};base64,{base64_file}"

        # تعريف الحقول المطلوب استخراجها
        prompt = (
            "Extract all items into JSON format with these exact keys: "
            "hs_code, description, qty, unit_price, amount, origin. "
            "Important: Keep Arabic text for description and origin. "
            "Return ONLY a valid JSON object with a single key 'items' containing the list."
        )

        # إرسال الطلب للموديل
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
        
        # تحويل النص المستلم إلى قاموس Python
        return json.loads(response.choices[0].message.content)

    except Exception as e:
        st.error(f"❌ فشل الاتصال بمحرك Mistral: {str(e)}")
        return None

# --- 4. واجهة المستخدم الرسومية ---
st.title("🚢 Clik-Plus | المستخرج الذكي")
st.markdown("تحليل الفواتير والمستندات باستخدام محرك **Pixtral AI**.")

# رفع الملف
uploaded_file = st.file_uploader("ارفع الفاتورة (صيغة PNG, JPG, JPEG)", type=['png', 'jpg', 'jpeg'])

if uploaded_file:
    # عرض معاينة للصورة المرفوعة
    with st.expander("👁️ معاينة المستند المرفوع"):
        st.image(uploaded_file, use_column_width=True)

    if st.button("🚀 تحليل واستخراج البيانات الآن"):
        with st.spinner("جاري تحليل المستند واستخراج البيانات..."):
            data = process_with_pixtral(uploaded_file.getvalue(), uploaded_file.type)
            
            if data and 'items' in data:
                # تحويل البيانات إلى DataFrame لعرضها بشكل جميل
                df = pd.DataFrame(data['items'])
                
                # عرض النتائج
                st.success(f"✅ تم استخراج {len(df)} صنف بنجاح!")
                st.dataframe(df, use_container_width=True)
                
                # إنشاء ملف Excel للتحميل
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df.to_excel(writer, index=False, sheet_name='ExtractedData')
                
                st.download_button(
                    label="📥 تحميل النتائج كملف Excel",
                    data=output.getvalue(),
                    file_name=f"Extracted_{uploaded_file.name}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.warning("⚠️ لم يتمكن المحرك من العثور على بيانات منظمة. حاول رفع صورة أكثر وضوحاً.")

# تذييل الصفحة
st.markdown("---")
st.caption("Clik-Plus Platform v2.0 - Powered by Mistral Pixtral")
