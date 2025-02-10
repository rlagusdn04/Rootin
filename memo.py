import tkinter as tk
from tkinter import ttk, simpledialog, messagebox
import json, os

# JSON 파일 경로
JSON_FILE = "tree_data.json"

# 트리 데이터를 JSON 파일에서 로드 (memo 필드 보장)
def load_tree():
    if os.path.exists(JSON_FILE):
        try:
            with open(JSON_FILE, "r", encoding="utf-8") as file:
                data = json.load(file)
                def ensure_memo(node):
                    if "memo" not in node:
                        node["memo"] = ""
                    for child in node.get("children", []):
                        ensure_memo(child)
                ensure_memo(data)
                return data
        except json.JSONDecodeError:
            messagebox.showerror("오류", "JSON 파일 형식 오류")
            return {"name": "Root", "memo": "", "children": []}
    else:
        return {"name": "Root", "memo": "", "children": []}

# 트리 데이터를 JSON 파일에 저장
def save_tree(data):
    with open(JSON_FILE, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=4, ensure_ascii=False)

# 전역 트리 데이터
tree_data = load_tree()

# --- Canvas 기반 트리 시각화 (좌측) ---

def draw_tree(canvas, node, x, y, x_offset):
    if not node:
        return
    # 노드 텍스트 그리기
    node_id = canvas.create_text(x, y, text=node["name"], font=("Arial", 12, "bold"), fill="black")
    
    # 노드를 클릭하면 자식 노드 추가 (기존에 루트 클릭 시 추가했던 기능)
    def on_canvas_click(event, current_node=node):
        new_name = simpledialog.askstring("노드 추가", f"'{current_node['name']}' 노드에 추가할 자식 노드 이름:")
        if new_name:
            current_node.setdefault("children", []).append({"name": new_name, "memo": "", "children": []})
            save_tree(tree_data)
            refresh_canvas()
            refresh_treeview()
    canvas.tag_bind(node_id, "<Button-1>", on_canvas_click)
    
    # 자식 노드 그리기 (부모 노드 중심 기준으로 좌우 배치)
    num_children = len(node.get("children", []))
    if num_children == 0:
        return
    start_x = x - (x_offset * (num_children - 1)) // 2
    child_y = y + 80  # 세로 간격
    for i, child in enumerate(node["children"]):
        child_x = start_x + i * x_offset
        canvas.create_line(x, y + 10, child_x, child_y - 10, fill="gray", arrow=tk.LAST)
        draw_tree(canvas, child, child_x, child_y, max(80, x_offset // 2))

# Canvas 새로 고침 함수
def refresh_canvas():
    vis_canvas.delete("all")
    width = vis_canvas.winfo_width() or 800
    draw_tree(vis_canvas, tree_data, width // 2, 50, 200)

# --- Treeview 및 메모 편집 (우측) ---

# Treeview 항목과 JSON 노드 객체 매핑용 딕셔너리
treeview_node_map = {}

def populate_treeview(treeview, parent, node):
    item_id = treeview.insert(parent, "end", text=node["name"], open=True)
    treeview_node_map[item_id] = node
    for child in node.get("children", []):
        populate_treeview(treeview, item_id, child)

def refresh_treeview():
    treeview.delete(*treeview.get_children())
    treeview_node_map.clear()
    populate_treeview(treeview, "", tree_data)

def on_treeview_select(event):
    selected = treeview.selection()
    if selected:
        node = treeview_node_map.get(selected[0])
        memo_text.delete("1.0", tk.END)
        memo_text.insert(tk.END, node.get("memo", ""))
    else:
        memo_text.delete("1.0", tk.END)

def save_memo():
    selected = treeview.selection()
    if selected:
        node = treeview_node_map.get(selected[0])
        node["memo"] = memo_text.get("1.0", tk.END).strip()
        save_tree(tree_data)
        messagebox.showinfo("저장", "메모가 저장되었습니다.")
    else:
        messagebox.showwarning("선택", "노드를 선택하세요.")

def add_node_treeview():
    selected = treeview.selection()
    if not selected:
        messagebox.showwarning("선택", "부모 노드를 선택하세요.")
        return
    parent_node = treeview_node_map.get(selected[0])
    new_name = simpledialog.askstring("노드 추가", "새로운 노드 이름:")
    if new_name:
        parent_node.setdefault("children", []).append({"name": new_name, "memo": "", "children": []})
        save_tree(tree_data)
        refresh_treeview()
        refresh_canvas()

# --- 초기화 기능 ---

def reset_tree():
    if messagebox.askyesno("초기화", "정말 초기화 하시겠습니까?\n기존 데이터는 모두 삭제됩니다."):
        global tree_data
        tree_data = {"name": "Root", "memo": "", "children": []}
        save_tree(tree_data)
        refresh_treeview()
        refresh_canvas()
        memo_text.delete("1.0", tk.END)
        messagebox.showinfo("초기화", "트리가 초기화되었습니다.")

# --- 메인 윈도우 및 레이아웃 구성 ---

root = tk.Tk()
root.title("트리 편집기 (동시 시각화 및 Treeview)")
root.geometry("1000x600")

# 좌측 프레임: Canvas 시각화와 초기화 버튼
left_frame = tk.Frame(root, bg="white")
left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

# 초기화 버튼 (좌측 상단에 배치)
reset_btn = tk.Button(left_frame, text="초기화", command=reset_tree)
reset_btn.pack(pady=5)

# Canvas 생성 (좌측 프레임)
vis_canvas = tk.Canvas(left_frame, bg="white")
vis_canvas.pack(fill=tk.BOTH, expand=True)

# Canvas 크기 변경 시 다시 그리기
def on_canvas_resize(event):
    refresh_canvas()
vis_canvas.bind("<Configure>", on_canvas_resize)

# 우측 프레임: Treeview와 메모 편집
right_frame = tk.Frame(root)
right_frame.pack(side=tk.RIGHT, fill=tk.BOTH)

treeview = ttk.Treeview(right_frame)
treeview.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
treeview.bind("<<TreeviewSelect>>", on_treeview_select)

# Treeview 관련 버튼 (노드 추가, 메모 저장)
btn_frame = tk.Frame(right_frame)
btn_frame.pack(fill=tk.X, padx=5, pady=5)
add_node_btn = tk.Button(btn_frame, text="노드 추가", command=add_node_treeview)
add_node_btn.pack(side=tk.LEFT, padx=5)
save_memo_btn = tk.Button(btn_frame, text="메모 저장", command=save_memo)
save_memo_btn.pack(side=tk.LEFT, padx=5)

# 메모 편집용 Text 위젯
memo_text = tk.Text(right_frame, height=10)
memo_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

# 초기 Treeview와 Canvas 그리기
refresh_treeview()
refresh_canvas()

root.mainloop()
