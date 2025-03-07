import os
import re
import json
from tkinter import Tk, filedialog
from openai import OpenAI
from pydantic import BaseModel

# 환경 변수로부터 OpenAI API 키 설정
api_key = os.environ.get("OPENAI_API_KEY")
if not api_key:
    print("환경 변수 OPENAI_API_KEY를 설정해주세요.")
    exit(1)

client = OpenAI(api_key=api_key)

# -------------------------------
# 1. Tkinter를 사용해 폴더 선택 (창을 항상 최상단에 표시)
# -------------------------------
root = Tk()
root.withdraw()  # 메인 윈도우 숨기기
root.attributes('-topmost', True)
root.update()

folder_path = filedialog.askdirectory(title="폴더를 선택하세요")
if not folder_path:
    print("폴더가 선택되지 않았습니다.")
    exit(0)

# -------------------------------
# 2. 선택한 폴더 내의 폴더명 중 영어로만 이루어진 폴더명 추출
#    (여기서는 알파벳과 공백만 허용하는 정규표현식 사용)
# -------------------------------
all_entries = os.listdir(folder_path)
english_folders = [d for d in all_entries if os.path.isdir(os.path.join(folder_path, d))
                   and re.fullmatch(r"[A-Za-z\s]+", d)]
if not english_folders:
    print("영어로만 이루어진 폴더명이 없습니다.")
    exit(0)

# -------------------------------
# 3. Pydantic 모델 정의 (structured output)
# -------------------------------
class FolderTranslation(BaseModel):
    original: str  # 원래 폴더명(영어)
    translated: str  # 번역된 폴더명(한국어)

class Translations(BaseModel):
    translations: list[FolderTranslation]

# -------------------------------
# 4. OpenAI API를 호출하여 폴더명 번역 요청
#    모델 버전은 "chatgpt-4.5"를 사용하며, 반드시 JSON 형식으로 출력하도록 시스템 프롬프트에서 안내함.
# -------------------------------
prompt = (
    "다음 영어 폴더명을 한국어로 번역해줘. "
    "출력은 반드시 JSON 형식으로 해줘. JSON 포맷 예시는 아래와 같아:\n"
    '{"translations": [{"original": "FolderName", "translated": "번역"}]}\n'
    f"폴더명 목록: {english_folders}"
)

print("OpenAI에 번역 요청 중입니다...")

completion = client.beta.chat.completions.parse(
    model="gpt-4.5-preview",
    messages=[
        {
            "role": "system",
            "content": "너는 영어 폴더명을 한국어로 번역하는 번역가야. 반드시 JSON 형식으로 결과를 출력해."
        },
        {
            "role": "user",
            "content": prompt
        }
    ],
    response_format=Translations,
    temperature=0
)

# OpenAI 응답에서 내용을 추출
translations_obj = completion.choices[0].message.parsed

# -------------------------------
# 5. 번역 결과를 사용자에게 출력하고, 직접 수정할 수 있도록 함
# -------------------------------
print("\n--- 번역 결과 ---")
for idx, item in enumerate(translations_obj.translations, start=1):
    print(f"{idx}. {item.original} -> {item.translated}")

while True:
    choice = input("\n수정을 원하는 번호를 입력하세요 (수정이 없으면 Enter 입력): ").strip()
    if not choice:
        break
    try:
        index = int(choice) - 1
        if index < 0 or index >= len(translations_obj.translations):
            print("잘못된 번호입니다. 다시 시도해주세요.")
            continue
        new_name = input(f"'{translations_obj.translations[index].original}'의 새로운 폴더명을 입력하세요: ").strip()
        if new_name:
            translations_obj.translations[index].translated = new_name
            print("수정 완료!")
    except ValueError:
        print("숫자를 입력해주세요.")

print("\n최종 폴더명 변경 목록:")
for item in translations_obj.translations:
    print(f"{item.original} -> {item.translated}")

confirm = input("\n위의 목록대로 폴더명을 변경하시겠습니까? (y/n): ").strip().lower()
if confirm != 'y':
    print("폴더명 변경을 취소합니다.")
    exit(0)

# -------------------------------
# 6. 실제 폴더명 변경 (os.rename 사용)
# -------------------------------
for item in translations_obj.translations:
    old_path = os.path.join(folder_path, item.original)
    new_path = os.path.join(folder_path, item.translated)
    try:
        os.rename(old_path, new_path)
        print(f"변경 완료: {item.original} -> {item.translated}")
    except Exception as e:
        print(f"변경 실패 ({item.original} -> {item.translated}):", e)
