import google.generativeai as genai

GEMINI_API_KEY = "AIzaSyBgYRya8IVvRgCX0TY_rY_cp8aLIxlQbkE"
genai.configure(api_key=GEMINI_API_KEY)

print("Mavjud modellar ro'yxati:")
try:
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(f"- {m.name}")
except Exception as e:
    print(f"Xatolik: {e}")
