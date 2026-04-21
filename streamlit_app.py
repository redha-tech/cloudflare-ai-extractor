import streamlit as st
import pandas as pd
import requests
import json
import re
import io

# جلب بيانات Cloudflare من الـ Secrets
CF_ID = st.secrets.get("CF_ACCOUNT_ID")
CF_TOKEN = st.secrets.get("CF_AUTH_TOKEN")

def process_with_cloudflare(text):
    url = f"https://api.cloudflare.com/client/v4/accounts/{CF_ID}/ai/run/@cf/meta/llama-3-8b-instruct"
    headers = {"Authorization": f"Bearer {CF_TOKEN}"}
    
    prompt = "Extract items to JSON. Keys: hs_code, description, qty, unit_price, amount, origin. Return ONLY JSON."
    
    payload = {
        "messages": [
            {"role": "system", "content": "You are a data expert. Output JSON only."},
            {"role": "user", "content": f"{prompt}\n\nDATA:\n{text}"}
        ]
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=25)
        result = response.json()
        if result.get("success"):
            # تنظيف النص المستخرج للتأكد من أنه JSON صالح
            raw_res = result["result"]["response"]
            match = re.search(r'\{.*\}', raw_res, re.DOTALL)
            return json.loads(match.group()) if match else None
    except:
        return None

st.title("🚀 Cloudflare AI Extractor")

uploaded_file = st.file_uploader("Upload Invoice (Excel/Text)", type=['xlsx', 'xls', 'txt'])

if uploaded_file:
    if uploaded_file.name.endswith(('.xlsx', '.xls')):
        text_data = pd.read_excel(uploaded_file).to_csv(index=False)
    else:
        text_data = uploaded_file.read().decode("utf-8")

    if st.button("Start Extraction"):
        with st.spinner("Processing..."):
            data = process_with_cloudflare(text_data)
            if data and 'items' in data:
                df = pd.DataFrame(data['items'])
                st.dataframe(df)
                
                # تجهيز ملف التحميل
                output = io.BytesIO()
                df.to_excel(output, index=False, engine='xlsxwriter')
                st.download_button("📥 Download Excel", output.getvalue(), "extracted.xlsx")
            else:
                st.error("Extraction failed. Check API Keys.")
