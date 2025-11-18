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
# 1. Tkinter를 사용해 최상위 폴더 선택 (깊이 1)
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
# 2. 선택한 폴더 내의 파일 중 한글이 포함되지 않은 파일만 추출 (깊이 1)
# -------------------------------
all_entries = os.listdir(folder_path)
english_files = [f for f in all_entries if os.path.isfile(os.path.join(folder_path, f))
                 and not re.search(r"[가-힣]", f)]
if not english_files:
    print("한글이 포함되지 않은 파일명이 없습니다.")
    exit(0)

# 파일명을 확장자 제외한 base 이름으로 그룹화
file_groups = {}
for filename in english_files:
    base, ext = os.path.splitext(filename)
    if base not in file_groups:
        file_groups[base] = []
    file_groups[base].append(ext)

unique_bases = list(file_groups.keys())

# -------------------------------
# 3. Pydantic 모델 정의 (구조화된 출력)
# -------------------------------
class FileTranslation(BaseModel):
    original: str  # 원래 파일명의 base (영어)
    translated: str  # 번역된 파일명의 base (한국어)

class Translations(BaseModel):
    translations: list[FileTranslation]

# -------------------------------
# 4. OpenAI API를 호출하여 base 이름 번역 요청 (한번만 호출)
#    모델은 반드시 JSON 형식으로 결과를 출력하도록 함.
# -------------------------------
prompt = (
    "다음 영어 파일명의 base 이름(확장자 제외)을 한국어로 번역해줘. "
    "출력은 반드시 JSON 형식으로 해줘. JSON 포맷 예시는 아래와 같아:\n"
    '{"translations": [{"original": "EnglishFile", "translated": "한국어파일"}]}\n'
    f"파일명 목록: {unique_bases}"
)

print("OpenAI에 번역 요청 중입니다...")

completion = client.chat.completions.parse(
    model="gpt-5.1",
    messages=[
        {
            "role": "system",
            "content": "너는 영어 파일명의 base 이름을 한국어로 번역하는 번역가야. 반드시 JSON 형식으로 결과를 출력해."
        },
        {
            "role": "user",
            "content": prompt
        }
    ],
    response_format=Translations,
    temperature=0,
    reasoning_effort="none"
)

# OpenAI 응답에서 내용을 추출
translations_obj = completion.choices[0].message.parsed

# -------------------------------
# 5. 번역 결과를 사용자에게 출력하고 직접 수정할 수 있도록 함
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
        new_name = input(f"'{translations_obj.translations[index].original}'의 새로운 파일명의 base를 입력하세요: ").strip()
        if new_name:
            translations_obj.translations[index].translated = new_name
            print("수정 완료!")
    except ValueError:
        print("숫자를 입력해주세요.")

print("\n최종 파일명 변경 목록:")
for item in translations_obj.translations:
    print(f"{item.original} -> {item.translated}")

confirm = input("\n위의 목록대로 파일명을 변경하시겠습니까? (y/n): ").strip().lower()
if confirm != 'y':
    print("파일명 변경을 취소합니다.")
    exit(0)

# -------------------------------
# 6. 실제 파일명 변경 (os.rename 사용)
#    파일의 base 이름만 변경하고 원래 확장자는 그대로 유지
# -------------------------------
for original_base, ext_list in file_groups.items():
    # 번역된 파일명의 base 찾기
    translation_entry = next((item for item in translations_obj.translations if item.original == original_base), None)
    if translation_entry:
        for ext in ext_list:
            old_filename = original_base + ext
            new_filename = translation_entry.translated + ext
            old_path = os.path.join(folder_path, old_filename)
            new_path = os.path.join(folder_path, new_filename)
            try:
                os.rename(old_path, new_path)
                print(f"변경 완료: {old_filename} -> {new_filename}")
            except Exception as e:
                print(f"변경 실패 ({old_filename} -> {new_filename}):", e)
