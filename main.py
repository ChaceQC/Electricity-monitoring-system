import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import threading
import re
import requests
from datetime import datetime
import time
import qqemail
import os


def send_email(email: str, title: str, content: str):
    try:
        qqemail.send_email(email, title, content)
    except Exception as e:
        print(f"邮件发送失败: {e}")


class LoginWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("校园电费系统登录")
        self.geometry("300x200")
        self.center_window()

        self.my_tokens = {}

        ttk.Label(self, text="学号：").pack(pady=5)
        self.username_entry = ttk.Entry(self)
        self.username_entry.pack(pady=5)

        ttk.Label(self, text="密码：").pack(pady=5)
        self.password_entry = ttk.Entry(self, show="*")
        self.password_entry.pack(pady=5)

        self.login_btn = ttk.Button(self, text="登录", command=self.do_login)
        self.login_btn.pack(pady=10)

    def center_window(self):
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() - width) // 2
        y = (self.winfo_screenheight() - height) // 2
        self.geometry(f'+{x}+{y}')

    def do_login(self):
        username = self.username_entry.get()
        password = self.password_entry.get()
        if not username or not password:
            messagebox.showwarning("输入错误", "请填写学号和密码")
            return

        login_url = "https://yktwx.hbue.edu.cn/berserker-auth/oauth/token"
        headers = {
            "Authorization": "Basic bW9iaWxlX3NlcnZpY2VfcGxhdGZvcm06bW9iaWxlX3NlcnZpY2VfcGxhdGZvcm1fc2VjcmV0",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        data = {
            "username": username,
            "password": password,
            "grant_type": "password",
            "scope": "all",
            "loginFrom": "h5",
            "logintype": "sno",
            "device_token": "h5",
            "synAccessSource": "h5"
        }

        try:
            response = requests.post(login_url, headers=headers, data=data)
            response.raise_for_status()
            self.my_tokens = response.json()
            self.destroy()
            app = ElectricFeeApp(self.my_tokens, password)
            app.mainloop()
        except Exception as e:
            messagebox.showerror("登录失败", f"错误信息: {str(e)}")


class SettingsWindow(tk.Toplevel):
    def __init__(self, parent, config):
        super().__init__(parent)
        self.title("系统设置")
        self.geometry("300x250")
        self.config = config

        ttk.Label(self, text="监控间隔（分钟）：").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.interval_entry = ttk.Entry(self)
        self.interval_entry.grid(row=0, column=1, padx=5, pady=5)
        self.interval_entry.insert(0, str(self.config['interval'] // 60))

        ttk.Label(self, text="告警阈值（元）：").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        self.threshold_entry = ttk.Entry(self)
        self.threshold_entry.grid(row=1, column=1, padx=5, pady=5)
        self.threshold_entry.insert(0, str(self.config['threshold']))

        self.auto_pay_var = tk.BooleanVar(value=self.config['auto_pay'])
        ttk.Checkbutton(self, text="自动缴费", variable=self.auto_pay_var).grid(row=2, column=0, columnspan=2, pady=5)

        ttk.Label(self, text="自动缴费金额：").grid(row=3, column=0, padx=5, pady=5, sticky=tk.W)
        self.auto_amount_entry = ttk.Entry(self)
        self.auto_amount_entry.grid(row=3, column=1, padx=5, pady=5)
        self.auto_amount_entry.insert(0, str(self.config['auto_amount']))

        ttk.Button(self, text="保存", command=self.save_settings).grid(row=4, column=0, columnspan=2, pady=10)

    def save_settings(self):
        try:
            interval = max(int(self.interval_entry.get()) * 60, 60)
            threshold = float(self.threshold_entry.get())
            auto_pay = self.auto_pay_var.get()
            auto_amount = float(self.auto_amount_entry.get())

            self.config.update({
                'interval': interval,
                'threshold': threshold,
                'auto_pay': auto_pay,
                'auto_amount': auto_amount
            })
            self.destroy()
        except ValueError:
            messagebox.showerror("输入错误", "请输入有效的数值")


class ElectricFeeApp(tk.Tk):
    def __init__(self, tokens, password):
        super().__init__()
        self.third_data_str = None
        self.third_data = None
        self.my_tokens = tokens
        self.password = password
        self.options_cache = {}
        self.monitoring = False
        self.timer = None
        self.config = {
            'interval': 1800,
            'threshold': 5.0,
            'auto_pay': False,
            'auto_amount': 40.0
        }

        self.init_ui()
        self.load_initial_data()

    def init_ui(self):
        self.title("电费监控系统")
        self.geometry("400x300")
        self.center_window()

        self.steps = [
            {"key": "campus", "prompt": "校区", "level": 0},
            {"key": "building", "prompt": "楼栋", "level": 1},
            {"key": "floor", "prompt": "楼层", "level": 2},
            {"key": "room", "prompt": "房间", "level": 3}
        ]

        self.comboboxes = []
        self.labels = []

        for i, step in enumerate(self.steps):
            label = ttk.Label(self, text=f"选择{step['prompt']}:")
            label.grid(row=i, column=0, padx=10, pady=5, sticky=tk.W)
            combobox = ttk.Combobox(self, state="disabled")
            combobox.grid(row=i, column=1, padx=10, pady=5, sticky=tk.EW)
            combobox.bind("<<ComboboxSelected>>", lambda e, idx=i: self.on_select(e, idx))
            self.labels.append(label)
            self.comboboxes.append(combobox)

        ttk.Label(self, text="通知邮箱:").grid(row=4, column=0, padx=10, pady=5, sticky=tk.W)
        self.email_entry = ttk.Entry(self)
        self.email_entry.grid(row=4, column=1, padx=10, pady=5, sticky=tk.EW)

        btn_frame = ttk.Frame(self)
        btn_frame.grid(row=5, column=0, columnspan=2, pady=10)
        ttk.Button(btn_frame, text="设置", command=self.open_settings).pack(side=tk.LEFT, padx=5)
        self.start_btn = ttk.Button(btn_frame, text="开始监控", command=self.start_monitoring)
        self.start_btn.pack(side=tk.LEFT, padx=5)
        self.stop_btn = ttk.Button(btn_frame, text="停止监控", command=self.stop_monitoring, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=5)

        self.status_var = tk.StringVar()
        ttk.Label(self, textvariable=self.status_var).grid(row=6, column=0, columnspan=2)
        self.result_var = tk.StringVar()
        ttk.Label(self, textvariable=self.result_var, wraplength=550).grid(row=7, column=0, columnspan=2)

        self.columnconfigure(1, weight=1)

    def center_window(self):
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() - width) // 2
        y = (self.winfo_screenheight() - height) // 2
        self.geometry(f"+{x}+{y}")

    def open_settings(self):
        SettingsWindow(self, self.config)

    def load_initial_data(self):
        threading.Thread(target=self.fetch_data, args=(0, {})).start()

    def fetch_data(self, level, params):
        try:
            request_data = {"feeitemid": "181", "type": "select", "level": level, **params}
            headers = self.get_headers()
            response = requests.post(
                "https://yktwx.hbue.edu.cn/charge/feeitem/getThirdData",
                headers=headers,
                data=request_data
            )
            data = response.json().get('map', {}).get('data', [])
            self.after(0, self.update_combobox, level, data)
        except Exception as e:
            self.after(0, messagebox.showerror, "错误", f"请求失败: {str(e)}")

    def get_headers(self):
        return {
            "synjones-auth": self.my_tokens['access_token'],
            "Authorization": "Basic Y2hhcmdlOmNoYXJnZV9zZWNyZXQ=",
            "Content-Type": "application/x-www-form-urlencoded",
            "Cookie": "error_times=0",
            "Host": "yktwx.hbue.edu.cn",
            "Origin": "https://yktwx.hbue.edu.cn",
            "Pragma": "no-cache",
            "Referer": "https://yktwx.hbue.edu.cn/charge-app/",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36 Edg/136.0.0.0",
            "dnt": "1",
            "sec-ch-ua": "\"Chromium\";v=\"136\", \"Microsoft Edge\";v=\"136\", \"Not.A/Brand\";v=\"99\"",
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": "\"Windows\"",
            "sec-gpc": "1",
        }

    def update_combobox(self, level, data):
        if not data:
            return
        # 保存选项映射关系
        self.options_cache[level] = {item['name']: item['value'] for item in data}
        self.comboboxes[level]['values'] = list(self.options_cache[level].keys())
        self.comboboxes[level]['state'] = 'readonly'
        # 禁用后续下拉框
        for i in range(level + 1, len(self.steps)):
            self.comboboxes[i]['values'] = []
            self.comboboxes[i]['state'] = 'disabled'

    def on_select(self, event, level):
        selected_name = event.widget.get()
        selected_value = self.options_cache[level].get(selected_name)
        if not selected_value:
            return

        # 构建请求参数
        params = {}
        for i in range(level + 1):
            current_name = self.comboboxes[i].get()
            params[self.steps[i]['key']] = self.options_cache[i][current_name]

        if level == len(self.steps) - 1:
            self.query_final_result(params)
        else:
            threading.Thread(target=self.fetch_data, args=(level + 1, params)).start()

    def query_final_result(self, data):
        try:
            headers = self.get_headers()
            response = requests.post(
                url="https://yktwx.hbue.edu.cn/charge/feeitem/getThirdData",
                headers=headers,
                data={"feeitemid": "181", "type": "IEC", **data}
            )
            resp_json = response.json()
            # print(resp_json)
            result = resp_json.get('map', {}).get('showData', {})
            self.third_data = resp_json['map']['data']
            self.third_data_str = "{"
            self.third_data_str += f"\"area\":\"{self.third_data['area']}\",\"buildingName\":\"{self.third_data['buildingName']}\",\"areaName\":\"{self.third_data['areaName']}\",\"floorName\":\"{self.third_data['floorName']}\",\"floor\":\"{self.third_data['floor']}\",\"aid\":\"{self.third_data['aid']}\",\"account\":\"{self.third_data['account']}\",\"building\":\"{self.third_data['building']}\",\"room\":\"{self.third_data['room']}\",\"roomName\":\"{self.third_data['roomName']}\",\"myCustomInfo\":\"房间：{self.third_data['areaName']} {self.third_data['buildingName']} {self.third_data['floorName']} {self.third_data['roomName']}\""
            self.third_data_str += "}"
            self.status_var.set(f"信息：{result.get('信息', '')}")
            self.result_var.set("")
        except Exception as e:
            messagebox.showerror("错误", f"查询失败: {str(e)}")

    def start_monitoring(self):
        if not self.validate_selections():
            return
        self.monitoring = True
        self.set_controls_state(False)
        self.start_btn['state'] = tk.DISABLED
        self.stop_btn['state'] = tk.NORMAL
        self.schedule_query()

    def stop_monitoring(self):
        self.monitoring = False
        if self.timer:
            self.after_cancel(self.timer)
        self.set_controls_state(True)
        self.start_btn['state'] = tk.NORMAL
        self.stop_btn['state'] = tk.DISABLED
        self.status_var.set("已停止监控！")
        self.check_balance_only_read()


    def schedule_query(self):
        if not self.monitoring:
            return
        threading.Thread(target=self.check_balance).start()
        self.timer = self.after(self.config['interval'] * 1000, self.schedule_query)
        next_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time() + self.config['interval']))
        self.status_var.set(f"下次查询时间: {next_time}")

    def check_balance_only_read(self):
        try:
            params = {}
            for i, step in enumerate(self.steps):
                current_name = self.comboboxes[i].get()
                params[step['key']] = self.options_cache[i][current_name]

            headers = self.get_headers()
            response = requests.post(
                "https://yktwx.hbue.edu.cn/charge/feeitem/getThirdData",
                headers=headers,
                data={"feeitemid": "181", "type": "IEC", **params}
            )
            result = response.json().get('map', {}).get('showData', {})
            fee_text = result.get('信息', '')
            fee = float(re.search(r'(\d+\.\d+)', fee_text).group(1))

            self.after(0, self.update_display, fee)
            print(fee, self.config['threshold'])
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("错误", str(e)))

    def check_balance(self):
        try:
            params = {}
            for i, step in enumerate(self.steps):
                current_name = self.comboboxes[i].get()
                params[step['key']] = self.options_cache[i][current_name]

            headers = self.get_headers()
            response = requests.post(
                "https://yktwx.hbue.edu.cn/charge/feeitem/getThirdData",
                headers=headers,
                data={"feeitemid": "181", "type": "IEC", **params}
            )
            result = response.json().get('map', {}).get('showData', {})
            fee_text = result.get('信息', '')
            fee = float(re.search(r'(\d+\.\d+)', fee_text).group(1))

            self.after(0, self.update_display, fee)
            print(fee, self.config['threshold'])
            if fee < self.config['threshold']:
                pay_msgs: str = ""
                if self.config['auto_pay']:
                    pay_msgs += f"已缴费{self.config['auto_amount']}元！"
                    self.auto_pay()
                self.send_alert(fee, pay_msgs)
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("错误", str(e)))

    def update_display(self, fee):
        time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.result_var.set(f"[{time_str}] 当前电费：{fee:.2f}元")

    def send_alert(self, fee, pay_msgs):
        email = self.email_entry.get()
        if '@' in email:
            threading.Thread(
                target=send_email,
                args=(email, "电费预警", f"当前电费余额{fee:.2f}元，已低于阈值{self.config['threshold']}元。{pay_msgs}")
            ).start()

    def auto_pay(self):
        try:
            pay_url = "https://yktwx.hbue.edu.cn/blade-pay/pay"

            pay_headers = \
                {
                    "Accept": "application/json, text/plain, */*",
                    "Accept-Encoding": "gzip, deflate, br, zstd",
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
                    "Authorization": "Basic Y2hhcmdlOmNoYXJnZV9zZWNyZXQ=",
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    # "Content-Length": "559",
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Cookie": "error_times=0",
                    "Host": "yktwx.hbue.edu.cn",
                    "Origin": "https://yktwx.hbue.edu.cn",
                    "Pragma": "no-cache",
                    "Referer": "https://yktwx.hbue.edu.cn/charge-app/",
                    "Sec-Fetch-Dest": "empty",
                    "Sec-Fetch-Mode": "cors",
                    "Sec-Fetch-Site": "same-origin",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36 Edg/136.0.0.0",
                    "dnt": "1",
                    "sec-ch-ua": "\"Chromium\";v=\"136\", \"Microsoft Edge\";v=\"136\", \"Not.A/Brand\";v=\"99\"",
                    "sec-ch-ua-mobile": "?0",
                    "sec-ch-ua-platform": "\"Windows\"",
                    "sec-gpc": "1",
                    "synjones-auth": self.my_tokens['access_token']
                }

            from urllib.parse import urlencode

            pay_data = \
                {
                    "feeitemid": "181",
                    "tranamt": 0.01,
                    "flag": "choose",
                    "source": "app",
                    "paystep": 0,
                    "abstracts": "",
                    "third_party": self.third_data_str
                }
            print(urlencode(self.third_data))

            tranamt = self.config['auto_amount']
            pay_data['tranamt'] = tranamt

            resp = requests.post(url=pay_url, headers=pay_headers, data=urlencode(pay_data, doseq=True))
            print(resp.json())
            first_data = resp.json()['data']

            get_url = "https://yktwx.hbue.edu.cn/charge/pay/getpayinfo"

            requests.get(url=get_url, headers=pay_headers, params={"orderid": first_data['orderid']})

            person_url = "https://yktwx.hbue.edu.cn/charge/order/personal_data"
            x = requests.get(url=person_url, headers=pay_headers, params={"orderid": first_data['orderid']})
            print(x.json())

            pay_data_2 = \
                {
                    "paytypeid": first_data['payList'][0]['id'],
                    "paytype": "CARDTSM",
                    "paystep": 2,
                    "orderid": first_data['orderid']
                }

            resp = requests.post(url=pay_url, headers=pay_headers, data=pay_data_2)
            print(resp.json())
            second_data = resp.json()['data']
            ps_key: str
            ps_value: str

            password_map = second_data['passwordMap']
            for key, value in password_map.items():
                ps_key = key
                ps_value: str = str(value)

            pay_data_3 = \
                {
                    "paytypeid": str(first_data['payList'][0]['id']),
                    "paytype": "CARDTSM",
                    "paystep": 2,
                    "orderid": str(first_data['orderid']),
                    "password": "",
                    "uuid": ps_key,
                    "isWX": 0
                }

            my_password = self.password
            to_password = ""

            # print(ps_value)

            for i in my_password:
                to_password += str(ps_value.find(i))

            # print(to_password)
            pay_data_3['password'] = to_password

            time_url = "https://yktwx.hbue.edu.cn/charge/order/getCurrentTime"

            requests.get(url=time_url, headers=pay_headers)

            resp = requests.post(url=pay_url, headers=pay_headers, data=pay_data_3)
            print(pay_data_3)
            final_data = resp.json()
            print(final_data)
            if final_data.get('success'):
                def update_msg():

                    old = self.result_var.get()
                    print(old)
                    self.result_var.set(f"{old}\n提示信息：自动缴费成功 {self.config['auto_amount']}元")
                    print(self.result_var.get())

                self.after(1000, self.check_balance_only_read) # 等待1s使后端数据更新
                self.after(5000, update_msg)  # 等待5s更新显示，避免冲突
        except Exception as e:
            messagebox.showerror("缴费失败", str(e))

    def validate_selections(self):
        for cb in self.comboboxes:
            if not cb.get():
                messagebox.showwarning("选择不完整", "请完成所有层级选择")
                return False
        if not self.email_entry.get():
            messagebox.showwarning("邮箱为空", "请输入邮箱")
            return False
        return True

    def set_controls_state(self, enabled):
        """设置控件状态"""
        state = 'readonly' if enabled else 'disabled'
        for combobox in self.comboboxes:
            combobox['state'] = state
        self.email_entry['state'] = 'normal' if enabled else 'disabled'


if __name__ == "__main__":
    login_window = LoginWindow()
    login_window.mainloop()
