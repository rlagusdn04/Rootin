import tkinter as tk
from tkinter import ttk, simpledialog, messagebox
import json, os, math, copy

# 전역 변수: 현재 줌 비율 (기본 1.0)
current_scale = 1.0

# -----------------------
# JSON 관련 함수 및 전역 데이터 (트리 구조)
# -----------------------
JSON_FILE = "tree_data.json"

def load_tree():
    if os.path.exists(JSON_FILE):
        try:
            with open(JSON_FILE, "r", encoding="utf-8") as file:
                data = json.load(file)
                if isinstance(data, dict):
                    data = [data]
                def ensure_memo(node):
                    if "memo" not in node:
                        node["memo"] = ""
                    for child in node.get("children", []):
                        ensure_memo(child)
                for node in data:
                    ensure_memo(node)
                return data
        except json.JSONDecodeError:
            messagebox.showerror("오류", "JSON 파일 형식 오류")
            return [{"name": "루트", "memo": "", "children": []}]
    else:
        return [{"name": "루트", "memo": "", "children": []}]

def save_tree(data):
    with open(JSON_FILE, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=4, ensure_ascii=False)

tree_data = load_tree()

# -----------------------
# Undo/Redo 기능
# -----------------------
undo_stack = []
redo_stack = []

def push_undo():
    global undo_stack, redo_stack, tree_data
    undo_stack.append(copy.deepcopy(tree_data))
    redo_stack.clear()

def undo():
    global tree_data, undo_stack, redo_stack
    if undo_stack:
        redo_stack.append(copy.deepcopy(tree_data))
        tree_data = undo_stack.pop()
        refresh_canvas()
        refresh_treeview()
    else:
        messagebox.showinfo("Undo", "더 이상 실행 취소할 내용이 없습니다.")

def redo():
    global tree_data, undo_stack, redo_stack
    if redo_stack:
        undo_stack.append(copy.deepcopy(tree_data))
        tree_data = redo_stack.pop()
        refresh_canvas()
        refresh_treeview()
    else:
        messagebox.showinfo("Redo", "더 이상 재실행할 내용이 없습니다.")

# -----------------------
# 헬퍼 함수: 부모 찾기 (트리 구조)
# -----------------------
def get_parent_recursive(node, target):
    for child in node.get("children", []):
        if child is target:
            return node
        p = get_parent_recursive(child, target)
        if p:
            return p
    return None

def get_parent_in_forest(forest, target):
    for node in forest:
        if node is target:
            return None
        p = get_parent_recursive(node, target)
        if p:
            return p
    return None

def get_parent(target):
    return get_parent_in_forest(tree_data, target)

def count_leaves(node):
    if not node.get("children"):
        return 1
    return sum(count_leaves(child) for child in node["children"])

# -----------------------
# 전역 변수 (캔버스 관련)
# -----------------------
canvas_node_map = {}   # {캔버스 항목 id: 노드 참조}
canvas_plus_map = {}   # {플러스 항목 id: 노드 참조}
arrow_map = {}         # {(부모 id, 자식 id): 선 id}

drag_data = {
    "node": None,
    "start_x": 0,
    "start_y": 0,
    "dragging": False,
}

# -----------------------
# 폰트 업데이트 (줌 시 텍스트 크기 갱신)
# -----------------------
def update_fonts():
    # 노드 이름 텍스트 (tag "node_group")
    for item in vis_canvas.find_withtag("node_group"):
        if vis_canvas.type(item) == "text":
            new_font = ("Arial", max(1, int(12 * current_scale)), "bold")
            vis_canvas.itemconfig(item, font=new_font)
    # 플러스 아이콘 (tag "plus")
    for item in vis_canvas.find_withtag("plus"):
        new_font = ("Arial", max(1, int(10 * current_scale)), "bold")
        vis_canvas.itemconfig(item, font=new_font)

# -----------------------
# Trash 영역 고정: 별도의 위젯으로 생성 (스크롤과 무관)
# -----------------------
def is_over_trash(x_root, y_root):
    # trash_frame는 전역 변수
    trash_x = trash_frame.winfo_rootx()
    trash_y = trash_frame.winfo_rooty()
    trash_width = trash_frame.winfo_width()
    trash_height = trash_frame.winfo_height()
    return (trash_x <= x_root <= trash_x + trash_width and 
            trash_y <= y_root <= trash_y + trash_height)

# -----------------------
# 유틸리티 함수들
# -----------------------
def show_context_menu(event):
    current = event.widget.find_withtag("current")
    if not current:
        return
    item = current[0]
    if item not in canvas_node_map:
        return
    node = canvas_node_map[item]
    context_menu = tk.Menu(root, tearoff=0)
    context_menu.add_command(label="메모 편집", command=lambda: open_memo_popup(node))
    context_menu.add_command(label="노드 수정", command=lambda: rename_node(node))
    context_menu.add_command(label="노드 삭제", command=lambda: delete_node(node))
    context_menu.add_command(label="자식 추가", command=lambda: add_child_node(node))
    context_menu.post(event.x_root, event.y_root)

# -----------------------
# 줌(마우스 휠) 기능 (노드, 연결선, 플러스 아이콘만 확대/축소; Trash 영역은 고정)
# -----------------------
def zoom(event):
    global current_scale
    if hasattr(event, 'delta'):
        scale_factor = 1.1 if event.delta > 0 else 0.9
    elif event.num == 4:
        scale_factor = 1.1
    elif event.num == 5:
        scale_factor = 0.9
    else:
        return

    x = vis_canvas.canvasx(event.x)
    y = vis_canvas.canvasy(event.y)
    vis_canvas.scale("node_group", x, y, scale_factor, scale_factor)
    vis_canvas.scale("plus", x, y, scale_factor, scale_factor)
    vis_canvas.scale("arrow_line", x, y, scale_factor, scale_factor)
    current_scale *= scale_factor
    update_fonts()
    bbox_all = vis_canvas.bbox("all")
    if bbox_all:
        vis_canvas.configure(scrollregion=bbox_all)

def rename_node(node):
    new_name = simpledialog.askstring("노드 수정", "새로운 이름을 입력하세요:", initialvalue=node["name"])
    if new_name:
        push_undo()
        node["name"] = new_name
        save_tree(tree_data)
        refresh_canvas()
        refresh_treeview()

def delete_node(node):
    push_undo()
    parent = get_parent(node)
    if parent is not None:
        try:
            parent["children"].remove(node)
        except ValueError:
            pass
    else:
        try:
            tree_data.remove(node)
        except ValueError:
            pass
    save_tree(tree_data)
    refresh_canvas()
    refresh_treeview()

def add_child_node(node):
    new_name = simpledialog.askstring("노드 추가", f"'{node['name']}' 노드에 추가할 자식 노드 이름:")
    if new_name:
        push_undo()
        node.setdefault("children", []).append({"name": new_name, "memo": "", "children": []})
        save_tree(tree_data)
        refresh_canvas()
        refresh_treeview()

def open_memo_popup(node):
    popup = tk.Toplevel(root)
    popup.title(f"메모 편집 - {node['name']}")
    text = tk.Text(popup, width=40, height=10)
    text.pack(padx=10, pady=10)
    text.insert(tk.END, node.get("memo", ""))
    def save_and_close():
        push_undo()
        node["memo"] = text.get("1.0", tk.END).strip()
        save_tree(tree_data)
        popup.destroy()
        refresh_treeview()
    btn = tk.Button(popup, text="저장", command=save_and_close)
    btn.pack(pady=5)

def on_plus_click(event):
    current = event.widget.find_withtag("current")
    if not current:
        return
    item = current[0]
    node = canvas_plus_map.get(item)
    if node:
        open_memo_popup(node)

def on_node_press(event):
    current = event.widget.find_withtag("current")
    if not current:
        return
    item = current[0]
    if item not in canvas_node_map:
        return
    drag_data["node"] = canvas_node_map[item]
    drag_data["start_x"] = event.x
    drag_data["start_y"] = event.y
    drag_data["dragging"] = False

def on_node_motion(event):
    if drag_data["node"] is None:
        return
    dx = event.x - drag_data["start_x"]
    dy = event.y - drag_data["start_y"]
    if math.sqrt(dx*dx + dy*dy) > 5:
        drag_data["dragging"] = True
        node_tag = f"node_{id(drag_data['node'])}"
        vis_canvas.move(node_tag, dx, dy)
        plus_tag = f"plus_{id(drag_data['node'])}"
        vis_canvas.move(plus_tag, dx, dy)
        drag_data["start_x"] = event.x
        drag_data["start_y"] = event.y
        drag_data["node"]["x"] = drag_data["node"].get("x", 0) + dx
        drag_data["node"]["y"] = drag_data["node"].get("y", 0) + dy
        update_arrows(drag_data["node"])

def on_node_release(event):
    if drag_data["node"] is None:
        return

    # 드래그 종료 시, 만약 마우스 포인터가 Trash 위젯 위에 있다면 삭제 처리
    if drag_data["dragging"] and is_over_trash(event.x_root, event.y_root):
        push_undo()
        parent = get_parent(drag_data["node"])
        if parent is not None:
            try:
                parent["children"].remove(drag_data["node"])
            except ValueError:
                pass
        else:
            try:
                tree_data.remove(drag_data["node"])
            except ValueError:
                pass
        save_tree(tree_data)
        refresh_treeview()
        refresh_canvas()
    elif drag_data["dragging"]:
        overlapping_items = vis_canvas.find_overlapping(event.x, event.y, event.x, event.y)
        target_node = None
        for item in overlapping_items:
            if item in canvas_node_map:
                candidate = canvas_node_map[item]
                if candidate is not drag_data["node"] and not is_descendant(drag_data["node"], candidate):
                    target_node = candidate
                    break
        if target_node:
            push_undo()
            original_parent = get_parent(drag_data["node"])
            if original_parent is not None:
                try:
                    original_parent["children"].remove(drag_data["node"])
                except ValueError:
                    pass
            target_node.setdefault("children", []).append(drag_data["node"])
            save_tree(tree_data)
            refresh_treeview()
            refresh_canvas()
        else:
            save_tree(tree_data)
    else:
        new_name = simpledialog.askstring("노드 추가", f"'{drag_data['node']['name']}' 노드에 추가할 자식 노드 이름:")
        if new_name:
            push_undo()
            drag_data["node"].setdefault("children", []).append({"name": new_name, "memo": "", "children": []})
            save_tree(tree_data)
            refresh_treeview()
            refresh_canvas()

    drag_data["node"] = None
    drag_data["dragging"] = False

def on_node_right_click(event):
    show_context_menu(event)

def is_descendant(parent, candidate):
    if parent is candidate:
        return True
    for child in parent.get("children", []):
        if is_descendant(child, candidate):
            return True
    return False

# -----------------------
# 화살표 연결 함수 (직선 연결)
# -----------------------
def get_connection_point(bbox, target_center):
    cx = (bbox[0] + bbox[2]) / 2
    cy = (bbox[1] + bbox[3]) / 2
    dx = target_center[0] - cx
    dy = target_center[1] - cy
    if dx == 0 and dy == 0:
        return cx, cy
    half_width = (bbox[2] - bbox[0]) / 2
    half_height = (bbox[3] - bbox[1]) / 2
    factor_x = half_width / abs(dx) if dx != 0 else float('inf')
    factor_y = half_height / abs(dy) if dy != 0 else float('inf')
    factor = min(factor_x, factor_y)
    return cx + dx * factor, cy + dy * factor

def update_arrows(node):
    parent = get_parent(node)
    if parent:
        key = (id(parent), id(node))
        if key in arrow_map:
            line_id = arrow_map[key]
            parent_bbox = vis_canvas.bbox(f"node_{id(parent)}")
            child_bbox = vis_canvas.bbox(f"node_{id(node)}")
            if parent_bbox and child_bbox:
                parent_center = ((parent_bbox[0] + parent_bbox[2]) / 2,
                                 (parent_bbox[1] + parent_bbox[3]) / 2)
                child_center = ((child_bbox[0] + child_bbox[2]) / 2,
                                (child_bbox[1] + child_bbox[3]) / 2)
                start_point = get_connection_point(parent_bbox, child_center)
                end_point = get_connection_point(child_bbox, parent_center)
                points = [start_point[0], start_point[1], end_point[0], end_point[1]]
                vis_canvas.coords(line_id, *points)
    for child in node.get("children", []):
        update_arrows(child)

# -----------------------
# 캔버스에 트리의 모든 노드 그리기 (재귀적으로)
# -----------------------
def draw_tree(canvas, node, x, y):
    if "x" in node and "y" in node:
        current_x, current_y = node["x"], node["y"]
    else:
        current_x, current_y = x, y
        node["x"] = x
        node["y"] = y

    node_tag = f"node_{id(node)}"
    base_font = ("Arial", max(1, int(12 * current_scale)), "bold")
    node_text_id = canvas.create_text(current_x, current_y, text=node["name"],
                                      font=base_font,
                                      fill="black", anchor="center",
                                      tags=("node_group", node_tag))
    canvas.update_idletasks()
    bbox = canvas.bbox(node_text_id)
    pad_x, pad_y = 4, 2
    rect_id = canvas.create_rectangle(bbox[0]-pad_x, bbox[1]-pad_y, bbox[2]+pad_x, bbox[3]+pad_y,
                                      fill="white", outline="black",
                                      tags=("node_group", node_tag))
    canvas.tag_raise(node_text_id, rect_id)
    canvas_node_map[node_text_id] = node
    canvas_node_map[rect_id] = node

    plus_margin = 8
    plus_x = bbox[2] + plus_margin
    plus_y = (bbox[1] + bbox[3]) / 2 - plus_margin
    plus_tag = f"plus_{id(node)}"
    plus_font = ("Arial", max(1, int(10 * current_scale)), "bold")
    plus_id = canvas.create_text(plus_x, plus_y, text="+",
                                 font=plus_font,
                                 fill="black", tags=("plus", plus_tag))
    canvas_plus_map[plus_id] = node
    canvas.tag_bind(plus_id, "<Button-1>", on_plus_click)

    children = node.get("children", [])
    if children:
        base_width = 80
        start_x = current_x - (len(children)-1) * base_width/2
        child_y = current_y + 80
        for child in children:
            if "x" not in child or "y" not in child:
                child["x"] = start_x
                child["y"] = child_y
            draw_tree(canvas, child, child["x"], child["y"])
            parent_bbox = canvas.bbox(node_tag)
            child_bbox = canvas.bbox(f"node_{id(child)}")
            if parent_bbox and child_bbox:
                parent_center = ((parent_bbox[0] + parent_bbox[2]) / 2, parent_bbox[3])
                child_top = ((child_bbox[0] + child_bbox[2]) / 2, child_bbox[1])
                points = [parent_center[0], parent_center[1], child_top[0], child_top[1]]
                line_id = canvas.create_line(*points, fill="gray", arrow=tk.LAST,
                                             tags=("arrow_line", f"arrow_{id(node)}_{id(child)}"))
                arrow_map[(id(node), id(child))] = line_id
            start_x += base_width

def bind_node_group_events(canvas):
    canvas.tag_bind("node_group", "<ButtonPress-1>", on_node_press)
    canvas.tag_bind("node_group", "<B1-Motion>", on_node_motion)
    canvas.tag_bind("node_group", "<ButtonRelease-1>", on_node_release)
    canvas.tag_bind("node_group", "<Button-3>", on_node_right_click)

def refresh_canvas():
    vis_canvas.delete("all")
    canvas_node_map.clear()
    canvas_plus_map.clear()
    arrow_map.clear()
    width = vis_canvas.winfo_width() or 800
    start_x = 100
    start_y = 50
    gap = 150
    for node in tree_data:
        draw_tree(vis_canvas, node, start_x, start_y)
        start_x += gap
    bind_node_group_events(vis_canvas)
    update_fonts()
    bbox_all = vis_canvas.bbox("all")
    if bbox_all:
        vis_canvas.configure(scrollregion=bbox_all)

# -----------------------
# 우측: Treeview 및 메모 편집 영역
# -----------------------
treeview_node_map = {}

def populate_treeview(tv, parent, node):
    item_id = tv.insert(parent, "end", text=node["name"], open=True)
    treeview_node_map[item_id] = node
    for child in node.get("children", []):
        populate_treeview(tv, item_id, child)

def refresh_treeview():
    treeview.delete(*treeview.get_children())
    treeview_node_map.clear()
    for node in tree_data:
        populate_treeview(treeview, "", node)

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
        push_undo()
        node = treeview_node_map.get(selected[0])
        node["memo"] = memo_text.get("1.0", tk.END).strip()
        save_tree(tree_data)
        messagebox.showinfo("저장", "메모가 저장되었습니다.")
    else:
        messagebox.showwarning("선택", "노드를 선택하세요.")

def add_node_treeview():
    push_undo()
    selected = treeview.selection()
    new_name = simpledialog.askstring("노드 추가", "새로운 노드 이름:")
    if not new_name:
        return
    if selected:
        parent_node = treeview_node_map.get(selected[0])
        parent_node.setdefault("children", []).append({"name": new_name, "memo": "", "children": []})
    else:
        tree_data.append({"name": new_name, "memo": "", "children": []})
    save_tree(tree_data)
    refresh_treeview()
    refresh_canvas()

def reset_tree():
    if messagebox.askyesno("초기화", "정말 초기화 하시겠습니까?\n기존 데이터는 모두 삭제됩니다."):
        global tree_data
        push_undo()
        tree_data = [{"name": "루트", "memo": "", "children": []}]
        save_tree(tree_data)
        refresh_treeview()
        refresh_canvas()
        memo_text.delete("1.0", tk.END)
        messagebox.showinfo("초기화", "트리가 초기화되었습니다.")

# -----------------------
# 메인 윈도우 및 레이아웃 (스크롤바 포함)
# -----------------------
root = tk.Tk()
root.title("트리 편집기 (스크롤 및 줌 기능, Trash 고정)")
root.geometry("1200x700")

# 왼쪽: 캔버스 영역 (노드 시각화) → 스크롤바 포함
left_frame = tk.Frame(root, bg="white")
left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

# 버튼 프레임 (초기화, Undo, Redo): 왼쪽 영역 위쪽에 위치
btn_frame_left = tk.Frame(left_frame, bg="white")
btn_frame_left.pack(side=tk.TOP, fill=tk.X)
reset_btn = tk.Button(btn_frame_left, text="초기화", command=reset_tree)
reset_btn.pack(side=tk.LEFT, padx=5, pady=5)
undo_btn = tk.Button(btn_frame_left, text="Undo", command=undo)
undo_btn.pack(side=tk.LEFT, padx=5, pady=5)
redo_btn = tk.Button(btn_frame_left, text="Redo", command=redo)
redo_btn.pack(side=tk.LEFT, padx=5, pady=5)

# 캔버스와 스크롤바 프레임
canvas_frame = tk.Frame(left_frame)
canvas_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

v_scroll = tk.Scrollbar(canvas_frame, orient=tk.VERTICAL)
v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
h_scroll = tk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL)
h_scroll.pack(side=tk.BOTTOM, fill=tk.X)

vis_canvas = tk.Canvas(canvas_frame, bg="white",
                       xscrollcommand=h_scroll.set, yscrollcommand=v_scroll.set)
vis_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

h_scroll.config(command=vis_canvas.xview)
v_scroll.config(command=vis_canvas.yview)

# Trash 영역: 별도의 위젯으로 left_frame에 고정 (스크롤과 무관)
trash_frame = tk.Frame(left_frame, width=100, height=100, bg="red")
trash_frame.place(relx=1.0, rely=1.0, anchor="se")
trash_label = tk.Label(trash_frame, text="Trash", fg="white", bg="red", font=("Arial", 12, "bold"))
trash_label.pack(expand=True, fill="both")

# 오른쪽: Treeview와 메모 편집 영역
right_frame = tk.Frame(root)
right_frame.pack(side=tk.RIGHT, fill=tk.BOTH)

treeview = ttk.Treeview(right_frame)
treeview.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
treeview.bind("<<TreeviewSelect>>", on_treeview_select)

btn_frame_right = tk.Frame(right_frame)
btn_frame_right.pack(fill=tk.X, padx=5, pady=5)
add_node_btn = tk.Button(btn_frame_right, text="노드 추가", command=add_node_treeview)
add_node_btn.pack(side=tk.LEFT, padx=5)
save_memo_btn = tk.Button(btn_frame_right, text="메모 저장", command=save_memo)
save_memo_btn.pack(side=tk.LEFT, padx=5)

memo_text = tk.Text(right_frame, height=10)
memo_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

refresh_treeview()
refresh_canvas()

# 휠 이벤트 바인딩 (Windows, macOS, Linux)
vis_canvas.bind("<MouseWheel>", zoom)
vis_canvas.bind("<Button-4>", zoom)
vis_canvas.bind("<Button-5>", zoom)

root.mainloop()
