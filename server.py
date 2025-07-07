import customtkinter as ctk
import a2s
import json
import threading
import time
import webbrowser

# --- 配置 ---
REFRESH_INTERVAL = 20  # 服务器信息刷新间隔（秒）
SQUEEZE_INTERVAL = 0.5  # 挤服时，每次尝试连接的间隔（秒）
WINDOW_TITLE = "CS2 服务器浏览器 & 挤服工具"


class ServerBrowserApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title(WINDOW_TITLE)
        self.geometry("600x750")

        # --- 新增：挤服状态管理 ---
        self.squeeze_thread = None
        self.squeezing_address = None
        self.stop_squeeze_flag = threading.Event()  # 用于安全停止线程的标志

        self.server_list = self.load_servers()
        self.server_widgets = {}

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.pack(pady=15, padx=20, fill="both", expand=True)

        title_label = ctk.CTkLabel(self.main_frame, text=WINDOW_TITLE, font=ctk.CTkFont(size=20, weight="bold"))
        title_label.pack(pady=10)

        self.scrollable_frame = ctk.CTkScrollableFrame(self.main_frame, label_text="服务器列表")
        self.scrollable_frame.pack(fill="both", expand=True, padx=5, pady=5)

        self.create_server_widgets()

        self.refresh_thread = threading.Thread(target=self.periodic_refresh, daemon=True)
        self.refresh_thread.start()

    def load_servers(self):
        try:
            with open("servers.json", "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return [{"name": "错误: 未找到 'servers.json'", "address": "127.0.0.1:27015"}]

    def create_server_widgets(self):
        for server in self.server_list:
            address = server["address"]

            server_frame = ctk.CTkFrame(self.scrollable_frame)
            server_frame.pack(pady=6, padx=10, fill="x")

            # 使用Grid布局以更好地对齐
            server_frame.grid_columnconfigure(0, weight=1)

            name_label = ctk.CTkLabel(server_frame, text=server["name"], font=ctk.CTkFont(size=14, weight="bold"),
                                      anchor="w")
            name_label.grid(row=0, column=0, padx=10, pady=(5, 0), sticky="w")

            info_label_players = ctk.CTkLabel(server_frame, text="玩家: -/-", anchor="w")
            info_label_players.grid(row=1, column=0, padx=10, sticky="w")

            info_label_map = ctk.CTkLabel(server_frame, text="地图: -", anchor="w")
            info_label_map.grid(row=2, column=0, padx=10, pady=(0, 5), sticky="w")

            # --- 新增：挤服状态标签 ---
            squeeze_status_label = ctk.CTkLabel(server_frame, text="", text_color="cyan", anchor="w")
            squeeze_status_label.grid(row=3, column=0, padx=10, pady=(0, 5), sticky="w")

            # --- 修改：按钮功能变为挤服/停止 ---
            squeeze_button = ctk.CTkButton(server_frame, text="挤 服", width=100,
                                           command=lambda addr=address: self.toggle_squeeze(addr))
            squeeze_button.grid(row=0, column=1, rowspan=4, padx=10, pady=5, sticky="e")

            self.server_widgets[address] = {
                "players": info_label_players,
                "map": info_label_map,
                "button": squeeze_button,
                "status": squeeze_status_label,  # 存储状态标签的引用
            }

    # --- 新增：核心挤服逻辑 ---
    def toggle_squeeze(self, address):
        # 如果当前正在挤服，并且点击的是同一个服务器的按钮（现在是“停止”按钮）
        if self.squeezing_address == address:
            self.stop_squeeze_process()
            return

        # 如果当前正在挤服，但用户点击了另一个服务器的按钮
        if self.squeezing_address is not None:
            # 可以选择弹窗提示，或直接忽略
            print("请先停止当前的挤服任务！")
            return

        # 开始新的挤服任务
        self.squeezing_address = address
        self.stop_squeeze_flag.clear()  # 重置停止标志

        self.squeeze_thread = threading.Thread(target=self.squeeze_loop, args=(address,), daemon=True)
        self.squeeze_thread.start()

        self.update_ui_for_squeeze_start(address)

    def squeeze_loop(self, address):
        """在后台线程中循环尝试连接"""
        print(f"[{address}] 开始挤服循环...")
        while not self.stop_squeeze_flag.is_set():
            self.after(0, self.update_squeeze_status, address, f"正在尝试连接... 下次尝试在 {SQUEEZE_INTERVAL}s 后")
            connect_url = f"steam://connect/{address}"
            webbrowser.open(connect_url)

            # 等待指定间隔，此方法可以被 Event.wait() 中断，但 time.sleep 更简单
            # 检查标志，以便能更快地响应停止信号
            self.stop_squeeze_flag.wait(SQUEEZE_INTERVAL)

        print(f"[{address}] 挤服循环已停止。")
        self.after(0, self.reset_squeeze_ui)

    def stop_squeeze_process(self):
        """设置标志以停止挤服循环"""
        if self.squeeze_thread and self.squeeze_thread.is_alive():
            self.stop_squeeze_flag.set()  # 发送停止信号
            print("正在停止挤服线程...")

    # --- 新增：UI更新辅助函数 ---
    def update_ui_for_squeeze_start(self, started_address):
        """当挤服开始时，更新所有按钮的状态"""
        for addr, widgets in self.server_widgets.items():
            if addr == started_address:
                widgets["button"].configure(text="停 止", fg_color="firebrick")
                widgets["status"].configure(text="▶ 已启动挤服任务...")
            else:
                widgets["button"].configure(state="disabled")

    def reset_squeeze_ui(self):
        """当挤服停止后，重置所有UI元素"""
        self.update_squeeze_status(self.squeezing_address, "已停止。")
        self.squeezing_address = None
        for addr, widgets in self.server_widgets.items():
            widgets["button"].configure(text="挤 服", state="normal", fg_color=("#3B8ED0", "#1F6AA5"))
            # widgets["status"].configure(text="") # 可选择保留“已停止”消息

    def update_squeeze_status(self, address, message):
        """线程安全地更新状态标签"""
        if address and address in self.server_widgets:
            self.server_widgets[address]["status"].configure(text=message)

    def periodic_refresh(self):
        while True:
            for server in self.server_list:
                address = server["address"]
                self.update_server_info(address)
            time.sleep(REFRESH_INTERVAL)

    def update_server_info(self, address):
        try:
            ip, port_str = address.split(":")
            port = int(port_str)
            info = a2s.info((ip, port), timeout=2.0)
            player_text = f"玩家: {info.player_count}/{info.max_players}"
            map_text = f"地图: {info.map_name}"
            is_online = True
        except Exception:
            player_text = "玩家: 离线"
            map_text = "地图: -"
            is_online = False

        self.after(0, self.update_widget_text, address, player_text, map_text, is_online)

    def update_widget_text(self, address, player_text, map_text, is_online):
        widgets = self.server_widgets.get(address)
        if widgets:
            widgets["players"].configure(text=player_text)
            widgets["map"].configure(text=map_text)
            # 只有在没有挤服任务时，才根据在线状态更新按钮
            if not self.squeezing_address:
                widgets["button"].configure(state="normal" if is_online else "disabled")


if __name__ == "__main__":
    app = ServerBrowserApp()
    app.mainloop()