import google.generativeai as genai
genai.configure(api_key="AIzaSyCbCdb14coa0r1IIICDp4pd4Ql_OCOs1FE")
for m in genai.list_models():
    if 'generateContent' in m.supported_generation_methods:
        print(m.name)