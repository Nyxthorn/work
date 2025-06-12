import pandas as pd
import xml.etree.ElementTree as ET
import xml.dom.minidom

def split_times(time_str):
    if not isinstance(time_str, str) or not time_str.strip():
        return []
    result = []
    curr_day = ''
    for part in time_str.split(','):
        part = part.strip()
        if len(part) >= 2 and part[0] in "월화수목금토일":
            curr_day = part[0]
            result.append(part)
        elif curr_day:
            result.append(curr_day + part)
        else:
            result.append(part)
    return result

file_path = input("변환할 엑셀 파일 경로를 입력하세요 (예: MainView.xlsx): ").strip()
if not file_path:
    print("파일 경로가 입력되지 않았습니다.")
    exit(1)


wanted_cols = ['과목명', '강의시간', '강의실']

df = pd.read_excel(file_path, engine="openpyxl")

df = df[[col for col in wanted_cols if col in df.columns]].copy()


missing = [col for col in wanted_cols if col not in df.columns]
if missing:
    print(f"엑셀 파일에 다음 열이 없습니다: {', '.join(missing)}")
    exit(1)

df.columns = ['Name', 'Time', 'Room']

lecture_data = []

for idx, row in df.iterrows():
    name = str(row['Name']).strip()
    times = split_times(row['Time'])
    rooms = [r.strip() for r in str(row['Room']).split(',') if r.strip()]

    if len(rooms) == 1:
        for t in times:
            lecture_data.append({'Name': name, 'Time': t, 'Room': rooms[0]})
    else:
        n_per_room = len(times) // len(rooms)
        remainder = len(times) % len(rooms)
        ti = 0
        for i, room in enumerate(rooms):
            cnt = n_per_room + (1 if i < remainder else 0)
            for t in times[ti:ti+cnt]:
                lecture_data.append({'Name': name, 'Time': t, 'Room': room})
            ti += cnt

root = ET.Element('Lectures')
for lec in lecture_data:
    lec_elem = ET.SubElement(root, 'Lecture')
    name_elem = ET.SubElement(lec_elem, 'Name')
    name_elem.text = lec['Name']
    time_elem = ET.SubElement(lec_elem, 'Time')
    time_elem.text = lec['Time']
    room_elem = ET.SubElement(lec_elem, 'Room')
    room_elem.text = lec['Room']

xml_str = ET.tostring(root, encoding='utf-8')
pretty_xml = xml.dom.minidom.parseString(xml_str).toprettyxml(indent="  ")

with open("lectures.xml", "w", encoding="utf-8") as f:
    f.write(pretty_xml)

print("변환 완료! → lectures.xml 파일 생성됨")
