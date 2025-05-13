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
        self.root.title("🌈 강의실 예약 관리 시스템")
        self.root.geometry("1200x800")
        self.root.minsize(1000, 600)
        self.root.configure(bg='#fff5f9')

        self.current_version = "1.1.4"
        self.repo_url = "https://github.com/Nyxthorn/work/releases"

        self.website_data = []
        self.manual_data = []
        self.buildings = self.get_building_list()
        self.building_dict = {name: code for code, name in self.buildings} if self.buildings else {}

        self.setup_style()
        self.setup_ui()
        if self.buildings:
            self.load_initial_data()
        else:
            messagebox.showerror("초기화 오류", "건물 목록을 불러올 수 없습니다. 인터넷 연결을 확인해주세요.")

    def clean_building_name(self, name):
        """건물 이름에서 앞의 숫자와 공백 제거"""
        return re.sub(r'^\d+\s*', '', name).strip()

    def setup_style(self):
        style = ttk.Style()
        style.theme_use('clam')

        style.configure('.', background='#fff5f9', foreground='#333333')
        style.configure('TFrame', background='#fff5f9')
        style.configure('TLabel', background='#fff5f9', font=('나눔바른고딕', 9))
        style.configure('TButton', 
                       font=('나눔바른고딕', 10, 'bold'),
                       padding=8,
                       relief="flat",
                       background="#ffd1dc",
                       foreground="#4a4a4a",
                       borderwidth=0)
        
        style.map("TButton",
                 background=[('active', '#ffb3c6')],
                 relief=[('pressed', 'sunken')])

        style.configure("Treeview",
                       font=('나눔바른고딕', 9),
                       rowheight=36,
                       background="#fff0f7",
                       fieldbackground="#fff0f7",
                       borderwidth=0)
        style.configure("Treeview.Heading",
                       font=('나눔바른고딕', 10, 'bold'),
                       background="#ffd1dc",
                       foreground="#4a4a4a",
                       relief="flat")
        style.map("Treeview",
                 background=[('selected', '#ffb3c6')],
                 foreground=[('selected', '#000')])
        
        style.configure("Treeview.EvenRow", background="#fff0f7")
        style.configure("Treeview.OddRow", background="#ffe6f2")
        style.configure("TCombobox", fieldbackground="#ffffff", background="#ffffff", arrowsize=12)
        style.configure("TEntry", fieldbackground="#ffffff")

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
        self.building_combo['values'] = [name for code, name in self.buildings]
        self.building_combo.pack(side=tk.LEFT, padx=5)
        self.building_combo.bind('<<ComboboxSelected>>', lambda e: self.refresh_data())

        btn_frame = ttk.Frame(control_frame)
        btn_frame.pack(side=tk.RIGHT, padx=10)
        ttk.Button(btn_frame, text="새로고침", command=self.refresh_data).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="사용 가능 조회", command=self.open_check_dialog).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="업데이트 확인", command=self.check_for_update).pack(side=tk.LEFT, padx=2)

        columns = ('source', 'building', 'room', 'time', 'person', 'status')
        self.tree = ttk.Treeview(main_frame, columns=columns, show='headings', selectmode='browse')

        for col, text, width, anchor in [
            ('source', '출처', 100, 'center'),
            ('building', '건물', 150, 'center'),
            ('room', '강의실', 80, 'center'),
            ('time', '사용시간', 250, 'w'),
            ('person', '신청자', 150, 'w'),
            ('status', '상태', 80, 'center'),
        ]:
            self.tree.heading(col, text=text, anchor=anchor)
            self.tree.column(col, width=width, anchor=anchor, stretch=True)

        ttk.Separator(main_frame, orient='horizontal').pack(fill='x', pady=5)
        self.tree.pack(fill=tk.BOTH, expand=True, pady=10, padx=10)

    def get_building_list(self):
        try:
            url = "https://kutis1.kyungnam.ac.kr/ADFF/AE/AE0561M.aspx"
            response = requests.get(url, verify=False)
            soup = BeautifulSoup(response.text, 'html.parser')
            return [
                (opt['value'], self.clean_building_name(opt.text.strip()))
                for opt in soup.select('#slct_arg_bldg_cd option') 
                if opt['value'] != '%'
            ]
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
                today = datetime.today()
                return datetime(today.year, today.month, today.day, *map(int, parts[:3]))
            else:
                raise ValueError(f"잘못된 시간 형식: {time_str}")
        except Exception as e:
            raise ValueError(f"시간 파싱 오류: {time_str} - {str(e)}")

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

        for idx, entry in enumerate(all_entries):
            tags = ('EvenRow',) if idx % 2 == 0 else ('OddRow',)
            time_str = f"{entry['start'].strftime('%Y.%m.%d %H:%M')} ~ {entry['end'].strftime('%H:%M')}"
            self.tree.insert('', 'end', values=(
                entry['source'], entry['building'], entry['room'], time_str,
                entry['person'], entry['status']
            ), tags=tags)

    def is_conflict(self, new_entry):
        for entry in self.website_data + self.manual_data:
            if entry['building'] == new_entry['building'] and entry['room'] == new_entry['room']:
                if not (new_entry['end'] <= entry['start'] or new_entry['start'] >= entry['end']):
                    return True
        return False

    def refresh_data(self):
        if self.building_var.get():
            selected_index = self.building_combo.current()
            if selected_index == -1:
                return
            code = self.buildings[selected_index][0]
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
        dialog.title("🕒 사용 가능 시간 확인")
        dialog.configure(bg='#fff5f9')
        dialog.geometry("400x250")
        dialog.resizable(False, False)
        
        main_win_x = self.root.winfo_x()
        main_win_y = self.root.winfo_y()
        main_win_width = self.root.winfo_width()
        main_win_height = self.root.winfo_height()
        dialog_width = 400
        dialog_height = 250
        x = main_win_x + (main_win_width // 2) - (dialog_width // 2)
        y = main_win_y + (main_win_height // 2) - (dialog_height // 2)
        dialog.geometry(f"+{x}+{y}")
        
        main_frame = ttk.Frame(dialog, padding=(25, 15, 15, 15))
        main_frame.pack(fill=tk.BOTH, expand=True)

        current_building = self.building_var.get()
        buildings = [name for code, name in self.buildings]
        
        entries = {}
        row = 0
        
        ttk.Label(main_frame, text="").grid(row=row, column=0, pady=5)
        row += 1
        
        ttk.Label(main_frame, text="건물").grid(row=row, column=0, padx=5, pady=3, sticky='w')
        building_cb = ttk.Combobox(main_frame, values=buildings, state='readonly')
        if current_building in buildings:
            building_cb.current(buildings.index(current_building))
        else:
            building_cb.current(0)
        building_cb.grid(row=row, column=1, padx=5, pady=3, sticky='ew')
        entries['building'] = building_cb
        row += 1

        ttk.Label(main_frame, text="강의실").grid(row=row, column=0, padx=5, pady=3, sticky='w')
        room_entry = ttk.Entry(main_frame)
        room_entry.grid(row=row, column=1, padx=5, pady=3, sticky='ew')
        entries['room'] = room_entry
        row += 1

        ttk.Label(main_frame, text="날짜").grid(row=row, column=0, padx=5, pady=3, sticky='w')
        date_entry = DateEntry(main_frame, date_pattern='yyyy-mm-dd')
        date_entry.grid(row=row, column=1, padx=5, pady=3, sticky='ew')
        entries['date'] = date_entry
        row += 1

        time_frame = ttk.Frame(main_frame)
        time_frame.grid(row=row, column=0, columnspan=2, pady=8, sticky='ew')
        
        ttk.Label(time_frame, text="시작 시간").pack(side=tk.LEFT, padx=(0,5))
        start_hour = ttk.Combobox(time_frame, width=3, values=[f"{i:02d}" for i in range(24)], state='readonly')
        start_hour.current(9)
        start_hour.pack(side=tk.LEFT)
        ttk.Label(time_frame, text=":").pack(side=tk.LEFT, padx=1)
        start_min = ttk.Combobox(time_frame, width=3, values=[f"{i:02d}" for i in range(0, 60, 5)], state='readonly')
        start_min.current(0)
        start_min.pack(side=tk.LEFT)
        
        ttk.Label(time_frame, text="   종료 시간").pack(side=tk.LEFT, padx=(15,5))
        end_hour = ttk.Combobox(time_frame, width=3, values=[f"{i:02d}" for i in range(24)], state='readonly')
        end_hour.current(18)
        end_hour.pack(side=tk.LEFT)
        ttk.Label(time_frame, text=":").pack(side=tk.LEFT, padx=1)
        end_min = ttk.Combobox(time_frame, width=3, values=[f"{i:02d}" for i in range(0, 60, 5)], state='readonly')
        end_min.current(0)
        end_min.pack(side=tk.LEFT)
        row += 1

        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=row, column=0, columnspan=2, pady=12)
        
        def validate_and_check():
            if not room_entry.get().strip():
                messagebox.showwarning("입력 누락", "강의실 번호를 입력해주세요!", parent=dialog)
                return
            self.check_availability(dialog, building_cb.get(), room_entry.get(), 
                                  date_entry.get(), start_hour.get(), start_min.get(),
                                  end_hour.get(), end_min.get())

        ttk.Button(btn_frame, text="사용 가능 확인", command=validate_and_check).pack(side=tk.LEFT, padx=5)

    def check_availability(self, dialog, building, room, date, sh, sm, eh, em):
        try:
            if not re.match(r'^\d+$', self.parse_room_number(room)):
                raise ValueError("강의실 번호가 유효하지 않습니다")

            # 건물 이름으로 코드 조회
            code = next((code for code, name in self.buildings if name == building), None)
            if not code:
                raise ValueError("유효하지 않은 건물 선택입니다")
                
            room = self.parse_room_number(room)
            start_time_str = f"{date} {sh}:{sm}"
            end_time_str = f"{date} {eh}:{em}"

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
                messagebox.showwarning("사용 불가", "해당 시간에 이미 예약이 존재합니다.", parent=dialog)
            else:
                messagebox.showinfo("사용 가능", "해당 시간은 사용 가능합니다!", parent=dialog)

        except ValueError as ve:
            messagebox.showerror("입력 오류", str(ve), parent=dialog)
        except Exception as e:
            messagebox.showerror("시스템 오류", f"오류 발생: {str(e)}", parent=dialog)

    def check_for_update(self):
        try:
            api_url = "https://api.github.com/repos/Nyxthorn/work/releases/latest"
            response = requests.get(api_url, timeout=5)
            response.raise_for_status()
            latest = response.json()
            
            current_version = self.current_version
            latest_tag = latest.get("tag_name", "").strip()
            
            version_match = re.search(r'v?(\d+\.\d+\.\d+)', latest_tag)
            if not version_match:
                raise ValueError(f"GitHub 태그 형식 오류: '{latest_tag}'")
                
            latest_version = version_match.group(1)
            
            def version_to_tuple(ver):
                return tuple(map(int, ver.split('.')))
            
            current_tuple = version_to_tuple(current_version)
            latest_tuple = version_to_tuple(latest_version)
            
            if latest_tuple > current_tuple:
                release_url = latest.get('html_url', self.repo_url)
                response = messagebox.askyesno(
                    "업데이트 확인",
                    f"새 버전 {latest_version}이 출시되었습니다!\n\n"
                    f"현재 버전: {current_version}\n"
                    f"최신 버전: {latest_version}\n\n"
                    "업데이트 페이지로 이동하시겠습니까?"
                )
                if response:
                    webbrowser.open(release_url)
            else:
                messagebox.showinfo(
                    "업데이트 확인",
                    f"현재 최신 버전을 사용 중입니다.\n\n"
                    f"현재 버전: {current_version}"
                )
                
        except requests.exceptions.RequestException as req_err:
            messagebox.showerror("연결 오류", f"서버 연결 실패: {str(req_err)}")
        except Exception as e:
            messagebox.showerror("오류 발생", f"업데이트 확인 실패: {str(e)}")

if __name__ == "__main__":
    root = tk.Tk()
    app = ClassroomReservationSystem(root)
    root.mainloop()
