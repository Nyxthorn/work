import tkinter as tk
from tkinter import ttk, messagebox
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from tkcalendar import DateEntry
import warnings
import re
import webbrowser

warnings.filterwarnings('ignore', category=requests.packages.urllib3.exceptions.InsecureRequestWarning)

class ClassroomReservationSystem:
    def __init__(self, root):
        self.root = root
        self.root.title("강의실 예약 관리 시스템")
        self.root.geometry("1200x800")
        self.root.minsize(1000, 600)

        self.current_version = "1.0.0"
        self.repo_url = "https://github.com/Nyxthorn/work/releases"

        self.website_data = []
        self.manual_data = []
        self.buildings = self.get_building_list()
        self.building_dict = {name: code for code, name in self.buildings}

        self.setup_ui()
        self.load_initial_data()

    def get_building_name(self, code):
        return next((name for c, name in self.buildings if c == code), "알 수 없음")

    def setup_ui(self):
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill=tk.X, pady=5)

        ttk.Label(control_frame, text="검색:").pack(side=tk.LEFT, padx=5)
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(control_frame, textvariable=self.search_var, width=40)
        search_entry.pack(side=tk.LEFT, padx=5)
        search_entry.bind('<KeyRelease>', lambda e: self.update_search())

        ttk.Label(control_frame, text="건물:").pack(side=tk.LEFT, padx=10)
        self.building_var = tk.StringVar()
        self.building_combo = ttk.Combobox(control_frame, textvariable=self.building_var)
        self.building_combo['values'] = [f"{code}:{name}" for code, name in self.buildings]
        self.building_combo.pack(side=tk.LEFT, padx=5)
        self.building_combo.bind('<<ComboboxSelected>>', lambda e: self.refresh_data())

        btn_frame = ttk.Frame(control_frame)
        btn_frame.pack(side=tk.RIGHT, padx=10)
        ttk.Button(btn_frame, text="새로고침", command=self.refresh_data).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="사용 가능 조회", command=self.open_check_dialog).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="삭제", command=self.delete_entry).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="업데이트 확인", command=self.check_for_update).pack(side=tk.LEFT, padx=2)

        columns = ('source', 'building', 'room', 'time', 'person', 'status', 'conflict')
        self.tree = ttk.Treeview(main_frame, columns=columns, show='headings', selectmode='browse')

        for col, text, width, anchor in [
            ('source', '출처', 100, 'center'),
            ('building', '건물', 150, 'center'),
            ('room', '강의실', 80, 'center'),
            ('time', '사용시간', 250, 'w'),
            ('person', '신청자', 150, 'w'),
            ('status', '상태', 80, 'center'),
            ('conflict', '충돌', 60, 'center')
        ]:
            self.tree.heading(col, text=text, anchor=anchor)
            self.tree.column(col, width=width, anchor=anchor)

        self.tree.pack(fill=tk.BOTH, expand=True)
        self.tree.tag_configure('conflict', background='#ffdddd')
        self.tree.tag_configure('invalid', background='#ffaaaa')

    def get_building_list(self):
        try:
            url = "https://kutis1.kyungnam.ac.kr/ADFF/AE/AE0561M.aspx"
            response = requests.get(url, verify=False)
            soup = BeautifulSoup(response.text, 'html.parser')
            return [(opt['value'], opt.text.strip()) 
                    for opt in soup.select('#slct_arg_bldg_cd option') 
                    if opt['value'] != '%']
        except Exception as e:
            messagebox.showerror("오류", f"건물 목록 조회 실패: {str(e)}")
            return []

    def load_initial_data(self):
        if self.buildings:
            self.building_combo.current(0)
            self.refresh_data()

    def parse_room_number(self, room_str):
        match = re.search(r'(\d+)(?!.*\d)', room_str)
        return match.group(1) if match else room_str

    def scrape_website_data(self, building_code):
        try:
            session = requests.Session()
            url = "https://kutis1.kyungnam.ac.kr/ADFF/AE/AE0561M.aspx"
            res = session.get(url, verify=False)
            soup = BeautifulSoup(res.text, 'html.parser')
            viewstate = soup.find('input', {'id': '__VIEWSTATE'})['value']
            event_val = soup.find('input', {'id': '__EVENTVALIDATION'})['value']
            view_gen = soup.find('input', {'id': '__VIEWSTATEGENERATOR'})['value']

            data = {
                '__VIEWSTATE': viewstate,
                '__EVENTVALIDATION': event_val,
                '__VIEWSTATEGENERATOR': view_gen,
                'slct_arg_bldg_cd': building_code,
                '__EVENTTARGET': 'slct_arg_bldg_cd'
            }

            res = session.post(url, data=data, verify=False)
            soup = BeautifulSoup(res.text, 'html.parser')

            result = []
            for row in soup.select('#dataGrid tr:not(:first-child)'):
                cols = row.find_all('td')
                if len(cols) >= 8:
                    time_str = cols[4].text.strip()
                    if ' ~ ' not in time_str:
                        continue
                    start_str, end_str = time_str.split(' ~ ')

                    try:
                        start_time = self.parse_time(start_str)
                        end_time = self.parse_time(end_str)
                    except ValueError:
                        continue

                    result.append({
                        'source': '웹사이트',
                        'building': self.get_building_name(building_code),
                        'room': self.parse_room_number(cols[1].text.strip()),
                        'time': time_str,
                        'person': cols[2].text.strip(),
                        'status': cols[7].text.strip(),
                        'conflict': False,
                        'start': start_time,
                        'end': end_time
                    })
            return result
        except Exception as e:
            messagebox.showerror("오류", f"데이터 조회 실패: {str(e)}")
            return []

    def parse_time(self, time_str):
        time_str = re.sub(r'[^0-9]', '.', time_str)
        parts = re.findall(r'\d+', time_str)
        try:
            if len(parts) >= 5:
                return datetime(*map(int, parts[:5]))
            elif len(parts) == 3:
                return datetime(*map(int, parts[:3]))
            else:
                raise ValueError
        except Exception as e:
            raise ValueError(f"시간 파싱 오류: {time_str}")

    def check_conflicts(self):
        time_dict = {}
        conflicts = set()

        for entry in self.website_data + self.manual_data:
            key = (entry['building'], entry['room'])
            time_dict.setdefault(key, []).append(entry)

        for key, entries in time_dict.items():
            entries.sort(key=lambda x: x['start'])
            for i in range(len(entries) - 1):
                if entries[i]['end'] > entries[i+1]['start']:
                    entries[i]['conflict'] = True
                    entries[i+1]['conflict'] = True
                    conflicts.update((id(entries[i]), id(entries[i+1])))
        return conflicts

    def update_display(self):
        self.check_conflicts()
        self.tree.delete(*self.tree.get_children())
        all_entries = sorted(self.website_data + self.manual_data, key=lambda x: x['start'])

        for entry in all_entries:
            tags = ['conflict'] if entry['conflict'] else []
            if entry['conflict'] and entry['source'] == '수동입력':
                tags.append('invalid')

            time_str = f"{entry['start'].strftime('%Y.%m.%d %H:%M')} ~ {entry['end'].strftime('%H:%M')}"
            self.tree.insert('', 'end', values=(
                entry['source'], entry['building'], entry['room'], time_str,
                entry['person'], entry['status'], '⚠️' if entry['conflict'] else ''
            ), tags=tuple(tags))

    def is_conflict(self, new_entry):
        for entry in self.website_data + self.manual_data:
            if entry['building'] == new_entry['building'] and entry['room'] == new_entry['room']:
                if not (new_entry['end'] <= entry['start'] or new_entry['start'] >= entry['end']):
                    return True
        return False

    def refresh_data(self):
        if self.building_var.get():
            code = self.building_var.get().split(':')[0]
            self.website_data = self.scrape_website_data(code)
            self.update_display()

    def delete_entry(self):
        selected = self.tree.selection()
        if not selected:
            return
        item = self.tree.item(selected[0])
        values = item['values']

        if values[0] == '수동입력':
            self.manual_data = [e for e in self.manual_data if not (
                e['building'] == values[1] and e['room'] == values[2] and e['person'] == values[4])]
            self.update_display()

    def update_search(self):
        query = self.search_var.get().lower()
        for item in self.tree.get_children():
            values = self.tree.item(item)['values']
            tags = () if any(query in str(v).lower() for v in values) else ('hidden',)
            self.tree.item(item, tags=tags)
        self.tree.tag_configure('hidden', background='#f0f0f0')

    def open_check_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("사용 가능 시간 확인")
        dialog.grab_set()

        entries = {}

        ttk.Label(dialog, text="건물").grid(row=0, column=0, padx=5, pady=2)
        building_names = [name for _, name in self.buildings]
        building_cb = ttk.Combobox(dialog, values=building_names, state='readonly')
        building_cb.current(0)
        building_cb.grid(row=0, column=1, padx=5, pady=2)
        entries['building'] = building_cb

        ttk.Label(dialog, text="강의실").grid(row=1, column=0, padx=5, pady=2)
        room_entry = ttk.Entry(dialog)
        room_entry.grid(row=1, column=1, padx=5, pady=2)
        entries['room'] = room_entry

        ttk.Label(dialog, text="날짜").grid(row=2, column=0, padx=5, pady=2)
        date_entry = DateEntry(dialog, date_pattern='yyyy-mm-dd')
        date_entry.grid(row=2, column=1, padx=5, pady=2)
        entries['date'] = date_entry

        def create_time_selector(row, label_text, key_prefix):
            ttk.Label(dialog, text=label_text).grid(row=row, column=0, padx=5, pady=2)
            hour_cb = ttk.Combobox(dialog, width=5, values=[f"{i:02d}" for i in range(24)], state='readonly')
            min_cb = ttk.Combobox(dialog, width=5, values=[f"{i:02d}" for i in range(0, 60, 5)], state='readonly')
            hour_cb.current(0)
            min_cb.current(0)
            hour_cb.grid(row=row, column=1, sticky='w', padx=(5, 0))
            min_cb.grid(row=row, column=1, sticky='e', padx=(0, 5))
            entries[f'{key_prefix}_hour'] = hour_cb
            entries[f'{key_prefix}_min'] = min_cb

        create_time_selector(3, "시작 시간", "start")
        create_time_selector(4, "종료 시간", "end")

        def check_availability():
            try:
                building = entries['building'].get()
                code = self.building_dict.get(building)
                room = self.parse_room_number(entries['room'].get())
                date = entries['date'].get()
                start_time_str = f"{date} {entries['start_hour'].get()}:{entries['start_min'].get()}"
                end_time_str = f"{date} {entries['end_hour'].get()}:{entries['end_min'].get()}"

                start_dt = self.parse_time(start_time_str)
                end_dt = self.parse_time(end_time_str)

                if start_dt >= end_dt:
                    raise ValueError("종료 시간이 시작 시간보다 빠릅니다.")

                check_entry = {
                    'building': building,
                    'room': room,
                    'start': start_dt,
                    'end': end_dt
                }

                if self.is_conflict(check_entry):
                    messagebox.showwarning("사용 불가", "해당 시간에 이미 예약이 존재합니다.")
                else:
                    messagebox.showinfo("사용 가능", "해당 시간은 사용 가능합니다!")

            except Exception as e:
                messagebox.showerror("오류", str(e))

        ttk.Button(dialog, text="사용 가능 확인", command=check_availability).grid(row=5, columnspan=2, pady=10)

    def check_for_update(self):
        try:
            api_url = "https://api.github.com/repos/Nyxthorn/work/releases/latest"
            response = requests.get(api_url, timeout=5)
            latest = response.json()
            latest_tag = latest.get("tag_name", "")
            latest_version = latest_tag.replace("reservation_system-", "").strip()

            if latest_version > self.current_version:
                if messagebox.askyesno("업데이트 확인", f"새 버전 {latest_version}이 있습니다.\n업데이트 페이지로 이동하시겠습니까?"):
                    webbrowser.open(self.repo_url)
            else:
                messagebox.showinfo("업데이트 확인", "현재 최신 버전을 사용 중입니다.")

        except Exception as e:
            messagebox.showerror("업데이트 오류", f"업데이트 확인 실패:\n{str(e)}")

if __name__ == "__main__":
    root = tk.Tk()
    app = ClassroomReservationSystem(root)
    root.mainloop()
