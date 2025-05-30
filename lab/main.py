import tkinter as tk
from tkinter import ttk, messagebox
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from tkcalendar import DateEntry
import warnings
import re
import webbrowser
from PIL import Image, ImageDraw, ImageTk
import asyncio
from pyppeteer import launch
from pyppeteer_stealth import stealth
import sys
import os
import platform
import winreg
import threading
import nest_asyncio
import xml.etree.ElementTree as ET

nest_asyncio.apply() 

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


warnings.filterwarnings('ignore', category=requests.packages.urllib3.exceptions.InsecureRequestWarning)

class RoundedButton(tk.Canvas):
    def __init__(self, parent, text, command, radius=20, bg='#ffd1dc', fg='#4a4a4a', **kwargs):
        super().__init__(parent, highlightthickness=0, **kwargs)
        self.command = command
        self.radius = radius
        self.bg = bg
        self.fg = fg
        self.hover_bg = '#ffb3c6'
        self.text = text
        self.width = kwargs.get('width', 100)
        self.height = kwargs.get('height', 36)
        self.bind("<Button-1>", self._on_click)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.draw_normal()

    def draw_normal(self):
        self.delete("all")
        img = Image.new("RGBA", (self.width, self.height), (0,0,0,0))
        draw = ImageDraw.Draw(img)
        draw.rounded_rectangle((0, 0, self.width-1, self.height-1), 
                              radius=self.radius, fill=self.bg, outline=self.bg)
        self.image = ImageTk.PhotoImage(img)
        self.create_image(0,0, image=self.image, anchor='nw')
        self.create_text(self.width/2, self.height/2, 
                        text=self.text, fill=self.fg, 
                        font=('나눔바른고딕', 10, 'bold'))

    def draw_hover(self):
        self.delete("all")
        img = Image.new("RGBA", (self.width, self.height), (0,0,0,0))
        draw = ImageDraw.Draw(img)
        draw.rounded_rectangle((0, 0, self.width-1, self.height-1), 
                              radius=self.radius, fill=self.hover_bg, outline=self.hover_bg)
        self.image = ImageTk.PhotoImage(img)
        self.create_image(0,0, image=self.image, anchor='nw')
        self.create_text(self.width/2, self.height/2, 
                        text=self.text, fill=self.fg, 
                        font=('나눔바른고딕', 10, 'bold'))

    def _on_click(self, event):
        self.command()

    def _on_enter(self, event):
        self.draw_hover()

    def _on_leave(self, event):
        self.draw_normal()

class ClassroomReservationSystem:
    def __init__(self, root):
        self.root = root
        self.root.title("경남대학교 공간 관리 시스템")
        self.root.geometry("1200x800")
        self.root.minsize(1000, 600)
        self.root.configure(bg='#fff5f9')
        
        self.loop = None
        self.async_thread = None
        self.stop_event = None  

        self.current_version = "1.3.0"
        self.repo_url = "https://github.com/Nyxthorn/work/releases"

        self.website_data = []
        self.manual_data = []
        self.lecture_data = []  # ★ XML 강의 데이터 저장
        self.buildings = self.get_building_list()
        self.building_dict = {name: code for code, name in self.buildings} if self.buildings else {}
        self.building_code_map = self.create_building_code_map()  # ★ 건물 코드 매핑

        self.setup_style()
        self.setup_ui()
        self.create_login_ui()
        self.login_frame.pack_forget()
        self.xml_url = "https://raw.githubusercontent.com/Nyxthorn/work/main/data.xml"  # XML 데이터 URL ★추가
        self.load_xml_data()  # ★ XML 데이터 로드 추가
        
        if self.buildings:
            self.load_initial_data()
        else:
            messagebox.showerror("초기화 오류", "건물 목록을 불러올 수 없습니다. 인터넷 연결을 확인해주세요.")

    def create_building_code_map(self):
        """XML 축약 건물 코드 매핑 생성"""
        return {
            # 기본 매핑 (축약 → 공식명)
            '1공': '제1공학관', 
            '4공': '제4공학관',
            '5공': '제5공학관(제2자연관)',
            '건': '건강과학관(제1자연관)',
            '교': '교육관',
            '경': '제1경영관(제1경상관)',
            '문': '문무관',
            '2경': '제2경영관(제2경상관)',
            '창': '창조관',
            '산': '산학협력관',
            '디': '디자인관',
            '법': '법정관',
            '예': '예술관',
            '고운': '고운관(인문관)',
            '성훈': '성훈관(제3공학관)',
            '국': '국제어학관(국제교육관)',
            '한': '한마관',
        
            # 역매핑 추가 (공식명 → 축약)
            '제1공학관': '1공',
            '제4공학관': '4공',
            '제5공학관(제2자연관)': '5공',
            '건강과학관(제1자연관)': '건',
            '교육관': '교',
            '제1경영관(제1경상관)': '경',
            '문무관': '문',
            '제2경영관(제2경상관)': '2경',
            '창조관': '창',
            '산학협력관': '산',
            '디자인관': '디',
            '법정관': '법',
            '예술관': '예',
            '고운관(인문관)': '고운',
            '성훈관(제3공학관)': '성훈',
            '국제어학관(국제교육관)': '국',
            '한마관': '한'
        }


    def load_xml_data(self, reference_date=None):
        try:
            response = requests.get(self.xml_url, verify=False, timeout=10)
            root = ET.fromstring(response.content)
            self.lecture_data.clear()

            for lecture in root.findall('Lecture'):
                name = lecture.find('Name').text.strip() if lecture.find('Name') is not None else "이름 없는 강의"
                try:
                    raw_times = lecture.find('Time').text.strip()
                    raw_rooms = lecture.find('Room').text.strip()

                    # 시간 코드 확장
                    expanded_times = []
                    for time_part in raw_times.split(','):
                        time_part = time_part.strip()
                        # 범위 처리 (예: 수1-3 → 수1,수2,수3)
                        if '-' in time_part:
                            day = time_part[0]
                            start_end = time_part[1:].split('-')
                            if len(start_end) == 2:
                                start, end = start_end
                                for i in range(int(start), int(end)+1):
                                    expanded_times.append(f"{day}{i}")
                        else:
                            expanded_times.append(time_part)

                    # 강의실 분할
                    rooms = [r.strip() for r in raw_rooms.split(',') if r.strip()]
                
                    # 강의실 개수 조정 (1개면 반복, 여러 개면 순환)
                    if len(rooms) == 0:
                        continue
                    if len(rooms) < len(expanded_times):
                        if len(rooms) == 1:
                            rooms = rooms * len(expanded_times)
                        else:
                            rooms += [rooms[-1]] * (len(expanded_times) - len(rooms))

                    for time_code, room in zip(expanded_times, rooms):
                        # 건물-호실 분리 로직 (정규식 사용)
                        match = re.match(r"^([가-힣a-zA-Z]+?)\-?(\d+)$", room)
                        if match:
                            building_part, room_number = match.groups()
                        else:
                            building_part, room_number = room, ""
                        
                        building = self.building_code_map.get(building_part, building_part)
                        
                        # 시간 파싱
                        time_ranges = self.parse_time_code(time_code, reference_date=reference_date)
                        for start, end in time_ranges:
                            self.lecture_data.append({
                                'building': building,
                                'room': room_number,
                                'start': start,
                                'end': end,
                                'source': '수업',
                                'name': name
                            })
                        print(f"XML 강의 시간: {start} ~ {end}") # 추가

                except Exception as e:
                    print(f"🚫 강의 '{name}' 처리 실패: {str(e)}")
                    continue
        except Exception as e:
            messagebox.showwarning("오류", f"XML 처리 실패: {str(e)}")

    
    def parse_time_code(self, time_code, reference_date=None, days_ahead=6):
        """
        숫자/문자 교시 통합 처리 파서
        - reference_date: 기준 날짜 (예: 사용자가 선택한 날짜)
        - weeks_ahead: 몇 주치 수업을 생성할지 (기본 26주 = 약 6개월)
        """
        try:
            time_code = str(time_code).strip().upper()
            if len(time_code) < 1:
                return []

            # 1. 요일 추출
            day_char = time_code[0]
            kor_to_eng = {'월':'M','화':'T','수':'W','목':'R','금':'F','토':'S','일':'U'}
            if day_char not in kor_to_eng:
                raise ValueError(f"잘못된 요일 코드: {time_code}")
            day_num = kor_to_eng[day_char]
            day_map = {'M':0, 'T':1, 'W':2, 'R':3, 'F':4, 'S':5, 'U':6}
            target_weekday = day_map[day_num]

            # 2. 기준 날짜 처리
            base_date = reference_date or datetime.today()
            #if reference_date:
            #    base_date = reference_date
            #else:
            #    base_date = datetime.today()

            # 3. 교시 추출
            period_str = time_code[1:]
            periods = []
            for part in period_str.split(','):
                part = part.strip()
                if '-' in part:
                    start, end = part.split('-', 1)
                    current = start
                    while True:
                        periods.append(current)
                        if current == end: break
                        current = str(int(current)+1) if current.isdigit() else chr(ord(current)+1)
                else:
                    periods.append(part)
    
            # 4. 시간 계산 
            time_ranges = []
            for day_offset in range(-days_ahead, days_ahead +1):
                current_date = base_date + timedelta(days=day_offset)
                
                if current_date.weekday() != target_weekday:
                    continue
                for period in periods:
                    if period.isdigit():
                        period_num = int(period)
                        if not 1 <= period_num <= 14: continue
                        start_time = current_date.replace(hour=9 + (period_num - 1), minute=0)
                        end_time = start_time + timedelta(minutes=50)
                    elif period.isalpha() and len(period) == 1:
                        idx = ord(period.upper()) - ord('A')
                        start_min = 540 + 105 * idx  # 09:00 기준
                        hours, mins = divmod(start_min, 60)
                        start_time = current_date.replace(hour=hours, minute=mins)
                        end_time = start_time + timedelta(minutes=75)
                    else:
                        continue
                    time_ranges.append((start_time, end_time))
                """for period in periods:
                    if period.isdigit():
                        period_num = int(period)
                        if not 1 <= period_num <= 14: continue
                        start_time = self.get_next_weekday(target_weekday, base_date) + timedelta(weeks=week)
                        start_time = start_time.replace(hour=9 + (period_num - 1), minute=0)
                        end_time = start_time + timedelta(minutes=50)
                    elif period.isalpha() and len(period) == 1:
                        period = period.upper()
                        if not ('A' <= period <= 'I'): continue
                        idx = ord(period) - ord('A')
                        start_min = 540 + 105 * idx  # 09:00 기준
                        hours, mins = divmod(start_min, 60)
                        start_time = self.get_next_weekday(target_weekday, base_date) + timedelta(weeks=week)
                        start_time = start_time.replace(hour=hours, minute=mins)
                        end_time = start_time + timedelta(minutes=75)
                    else:
                        continue
                    time_ranges.append((start_time, end_time))"""
            return time_ranges
        except Exception as e:
            print(f"⚠️ 시간 코드 오류: {time_code} ({str(e)})")
            return []

    def get_next_weekday(self, target_weekday, from_date=None):
        """지정된 날짜 기준으로 다음 주의 특정 요일 반환"""
        if from_date is None:
            from_date = datetime.today()
        delta = (target_weekday - from_date.weekday() + 7) % 7
        return (from_date + timedelta(days=delta)).replace(hour=0, minute=0, second=0, microsecond=0)

    def is_time_overlap(self, entry1, entry2):
        """두 시간 항목이 겹치는지 확인"""
        return (entry1['start'] < entry2['end']) and (entry1['end'] > entry2['start'])

    def check_chrome_installed(self):
        try:
            if platform.system() == 'Windows':
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe")
                path, _ = winreg.QueryValueEx(key, None)
                winreg.CloseKey(key)
                return os.path.exists(path)
        except:
            pass
        
        common_paths = [
            os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
        ]
        
        for path in common_paths:
            if os.path.exists(path):
                return True
        return False

    def find_chrome_path(self):
        try:
            if platform.system() == 'Windows':
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe")
                path, _ = winreg.QueryValueEx(key, None)
                winreg.CloseKey(key)
                if os.path.exists(path):
                    return path
        except:
            pass
        
        common_paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ]
        
        for path in common_paths:
            if os.path.exists(path):
                return path
        return None

    def load_initial_data(self):
        if self.buildings:
            self.building_combo.current(0)
            self.refresh_data()

    def clean_building_name(self, name):
        return re.sub(r'^\d+\s*', '', name).strip()

    def setup_style(self):
        style = ttk.Style()
        style.theme_use('clam')

        style.configure('.', background='#fff5f9', foreground='#333333')
        style.configure('TFrame', background='#fff5f9')
        style.configure('TLabel', background='#fff5f9', font=('나눔바른고딕', 9))
        style.configure('TEntry', fieldbackground='#ffffff')
        
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
        
        self.apply_btn = RoundedButton(btn_frame, text="공간사용신청", 
                                     command=self.toggle_login_frame, 
                                     width=120, height=36)
        self.apply_btn.pack(side=tk.LEFT, padx=2)
        
        self.refresh_btn = RoundedButton(btn_frame, text="새로고침", 
                                       command=self.refresh_data, 
                                       width=100, height=36)
        self.refresh_btn.pack(side=tk.LEFT, padx=2)
        
        self.check_btn = RoundedButton(btn_frame, text="사용 가능 조회", 
                                     command=self.open_check_dialog, 
                                     width=120, height=36)
        self.check_btn.pack(side=tk.LEFT, padx=2)
        
        self.update_btn = RoundedButton(btn_frame, text="업데이트 확인", 
                                      command=self.check_for_update, 
                                      width=120, height=36)
        self.update_btn.pack(side=tk.LEFT, padx=2)

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

    def toggle_login_frame(self):
        if self.login_frame.winfo_ismapped():
            self.login_frame.pack_forget()
        else:
            self.login_frame.pack(padx=10, pady=10)

    def create_login_ui(self):
        self.login_frame = ttk.Frame(self.root, style='TFrame')
        
        ttk.Label(self.login_frame, text="아이디").grid(row=0, column=0, padx=5, pady=5)
        self.entry_id = ttk.Entry(self.login_frame)
        self.entry_id.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(self.login_frame, text="비밀번호").grid(row=1, column=0, padx=5, pady=5)
        self.entry_pw = ttk.Entry(self.login_frame, show="*")
        self.entry_pw.grid(row=1, column=1, padx=5, pady=5)

        self.btn_login = RoundedButton(self.login_frame, text="로그인", 
                                      command=self.login, 
                                      width=80, height=30)
        self.btn_login.grid(row=2, column=0, columnspan=2, pady=10)

    async def async_login(self, user_id, user_pw):
        browser = None
        page = None
        try:
            chrome_path = self.find_chrome_path()
            if not chrome_path:
                raise Exception("Chrome 브라우저를 찾을 수 없습니다.")

            # 브라우저 실행 (사용자 수동 종료)
            browser = await launch(
                executablePath=chrome_path,
                headless=False,
                handleSIGINT=False,
                handleSIGTERM=False,
                handleSIGHUP=False,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--window-size=1280,720'
                ],
                ignoreHTTPSErrors=True,
                autoClose=False
            )

            page = await browser.newPage()
            await page.setViewport({'width': 1280, 'height': 720})
            await stealth(page)

            # 로그인 프로세스
            await page.goto('https://kutis1.kyungnam.ac.kr/ADFF/AE/AE_Login.aspx', timeout=60000)
            
            # 사용자 타입 선택
            await page.click('#rdoUserType_1')
            
            # 아이디, 비밀번호 박스 선택
            await page.type('#txtUserID', user_id, delay=30)
            await page.type('#txtPassword', user_pw, delay=30)
            
            # 네비게이션 대기
            await asyncio.gather(
                page.waitForNavigation({'waitUntil': 'networkidle2', 'timeout': 30000}),
                page.click('#ibtnLogin')
            )

            # 공간신청 페이지 이동
            await page.goto(
                'https://kutis1.kyungnam.ac.kr/ADFF/AE/AE0560M.aspx',
                {'waitUntil': 'domcontentloaded', 'timeout': 30000}
            )
            
            # 성공 알림
            self.root.after(0, lambda: messagebox.showinfo("성공", "브라우저에서 신청을 진행해주세요"))
            return True

        except Exception as e:
            # 오류 발생 시 브라우저 스크린샷 저장
            if page:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                await page.screenshot({'path': f'login_error_{timestamp}.png'})
            raise e

    def start_async_loop(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def safe_gui_update(self, func, *args):
        self.root.after(0, lambda: func(*args))

    def login(self):
        if not self.check_chrome_installed():
            response = messagebox.askyesno(
                "Chrome 설치 필요",
                "이 기능을 사용하려면 Google Chrome 브라우저가 필요합니다.\n"
                "설치 페이지로 이동하시겠습니까?"
            )
            if response:
                webbrowser.open("https://www.google.com/chrome/")
            return

        user_id = self.entry_id.get()
        user_pw = self.entry_pw.get()
    
        if not user_id or not user_pw:
            messagebox.showerror("오류", "아이디와 비밀번호를 입력하세요.")
            return

        async def async_task():
            try:
                await self.async_login(user_id, user_pw)
                self.safe_gui_update(messagebox.showinfo, "성공", "브라우저에서 신청을 진행해주세요")
                self.safe_gui_update(self.login_frame.pack_forget)
            except Exception as e:
                self.safe_gui_update(messagebox.showerror, "실패", str(e))

        def run_async():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(async_task())
        import threading
        threading.Thread(target=run_async, daemon=True).start()

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

    def parse_room_number(self, room_str):
        #match = re.search(r'(\d+)(?!.*\d)', room_str)
        #return match.group(1) if match else room_str
        return re.sub(r'[^0-9]', '', room_str)

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
        """강화된 충돌 검사 로직"""
        # 건물명 정규화
        new_building = self.building_code_map.get(new_entry['building'], new_entry['building'])
        new_room = self.parse_room_number(new_entry['room'])
    
        print(f"\n=== 충돌 검사 시작 ===")
        print(f"신청 건물: {new_building}, 호실: {new_room}")
        print(f"신청 시간: {new_entry['start']} ~ {new_entry['end']}")

        for entry in self.lecture_data + self.website_data + self.manual_data:
            # 건물명 정규화
            entry_building = self.building_code_map.get(entry['building'], entry['building'])
            entry_room = self.parse_room_number(entry['room'])
        
            # 건물 & 호실 비교
            if entry_building != new_building or entry_room != new_room:
                continue
            print(f"비교 건물: {entry_building} vs {new_building}")# 추가
            print(f"비교 호실: {entry_room} vs {new_room}")# 추가
            # 시간 비교
            if self.is_time_overlap(entry, new_entry):
                print(f"🚨 충돌 발견: {entry['source']} {entry['start']}~{entry['end']}")
                return entry['source']
    
        print("✅ 충돌 없음")
        return False
        
    def refresh_data(self):
        """새로고침 시 XML 데이터도 함께 갱신"""
        try:
            # 기존 데이터 초기화
            self.website_data = []
            self.manual_data = []
            self.lecture_data = []

            # 건물 목록 재로드
            self.buildings = self.get_building_list()
            self.building_dict = {name: code for code, name in self.buildings}

            # 데이터 재로드
            self.load_xml_data()
            if self.building_var.get():
                selected_index = self.building_combo.current()
                code = self.buildings[selected_index][0]
                self.website_data = self.scrape_website_data(code)
                self.update_display()
            messagebox.showinfo("새로고침 완료", "최신 데이터로 갱신되었습니다.")
        except Exception as e:
            messagebox.showerror("새로고침 오류", f"데이터 갱신 실패: {str(e)}")

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

        check_btn = RoundedButton(btn_frame, text="사용 가능 확인", 
                                command=validate_and_check, 
                                width=120, height=36)
        check_btn.pack(side=tk.LEFT, padx=5)

    def check_availability(self, dialog, building, room, date, sh, sm, eh, em):
        try:
            if not re.match(r'^\d+$', self.parse_room_number(room)):
                raise ValueError("강의실 번호가 유효하지 않습니다")

            code = next((code for code, name in self.buildings if name == building), None)
            if not code:
                raise ValueError("유효하지 않은 건물 선택입니다")
                
            reference_date = datetime.strptime(date, "%Y-%m-%d")
            self.load_xml_data(reference_date=reference_date)
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

            conflict_source = self.is_conflict(check_entry)
            if conflict_source:
                msg_map = {
                    '웹사이트': "🚨 이미 예약된 시간입니다!",
                    '수업': "📖 정규 수업 시간과 중복됩니다!",
                    '수동입력': "🖋️ 수동 입력된 예약이 있습니다!"
                }
                messagebox.showwarning(
                    "사용 불가", 
                    f"{msg_map.get(conflict_source, '')}\n\n"
                    f"• 건물: {building}\n"
                    f"• 강의실: {room}\n"
                    f"• 충돌 시간: {start_dt.strftime('%m/%d %H:%M')}~{end_dt.strftime('%H:%M')}",
                    parent=dialog
                )
            else:
                messagebox.showinfo(
                    "사용 가능", 
                    "✅ 해당 시간은 사용 가능합니다!\n\n"
                    f"• 건물: {building}\n"
                    f"• 강의실: {room}\n"
                    f"• 신청 시간: {start_dt.strftime('%m/%d %H:%M')}~{end_dt.strftime('%H:%M')}",
                    parent=dialog
                )

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
    import nest_asyncio
    nest_asyncio.apply()
    root = tk.Tk()
    app = ClassroomReservationSystem(root)
    
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    def on_closing():
        root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()
