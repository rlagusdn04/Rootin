import tkinter as tk
from tkinter import ttk, simpledialog, messagebox
import json, os, math, copy

# =======================
# JSON 관련 함수 및 전역 데이터
# =======================
JSON_FILE = "tree_data.json"

def load_tree():
    if os.path.exists(JSON_FILE):
        try:
            with open(JSON_FILE, "r", encoding="utf-8") as file:
                data = json.load(file)
                # 모든 노드에 memo 필드가 없는 경우 추가
                def ensure_memo(node):
                    if "memo" not in node:
                        node["memo"] = ""
                    for child in node.get("children", []):
                        ensure_memo(child)
                ensure_memo(data)
                return data
        except json.JSONDecodeError:
            messagebox.showerror("오류", "JSON 파일 형식 오류")
            return {"name": "루트", "memo": "", "children": []}
    else:
        return {"name": "루트", "memo": "", "children": []}

def save_tree(data):
    with open(JSON_FILE, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=4, ensure_ascii=False)

tree_data = load_tree()

# =======================
# Undo/Redo 기능
# =======================
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

# =======================
# 헬퍼 함수: 부모 찾기, 리프 노드 계산
# =======================
def get_parent(root, target):
    if root is target:
        return None
    for child in root.get("children", []):
        if child is target:
            return root
        parent = get_parent(child, target)
        if parent:
            return parent
    return None

def count_leaves(node):
    if not node.get("children"):
        return 1
    return sum(count_leaves(child) for child in node["children"])

# =======================
# 전역 변수 (Canvas 관련)
# =======================
canvas_node_map = {}  # {canvas_item_id: node_ref}
canvas_plus_map = {}  # {plus_item_id: node_ref}
arrow_map = {}        # {(parent_id, child_id): line_id}

drag_data = {
    "node": None,           # 드래그 중인 노드의 JSON 데이터
    "start_x": 0,
    "start_y": 0,
    "dragging": False,
}

# =======================
# 유틸리티 함수들
# =======================
def highlight_node(item):
    # 필요시 구현
    pass

def clear_highlight():
    # 필요시 구현
    pass

def show_context_menu(event):
    item = event.widget.find_withtag("current")[0]
    if item not in canvas_node_map:
        return
    node = canvas_node_map[item]
    context_menu = tk.Menu(root, tearoff=0)
    context_menu.add_command(label="메모 편집", command=lambda: open_memo_popup(node))
    context_menu.add_command(label="노드 수정", command=lambda: rename_node(node))
    if node is not tree_data:
        context_menu.add_command(label="노드 삭제", command=lambda: delete_node(node))
    context_menu.add_command(label="자식 추가", command=lambda: add_child_node(node))
    context_menu.post(event.x_root, event.y_root)

def rename_node(node):
    new_name = simpledialog.askstring("노드 수정", "새로운 이름을 입력하세요:", initialvalue=node["name"])
    if new_name:
        push_undo()
        node["name"] = new_name
        save_tree(tree_data)
        refresh_canvas()
        refresh_treeview()

def delete_node(node):
    if node is tree_data:
        messagebox.showwarning("삭제 불가", "루트 노드는 삭제할 수 없습니다.")
        return
    push_undo()
    parent = get_parent(tree_data, node)
    if parent:
        try:
            parent["children"].remove(node)
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
    item = event.widget.find_withtag("current")[0]
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
        # 노드의 좌표 업데이트
        drag_data["node"]["x"] = drag_data["node"].get("x", 0) + dx
        drag_data["node"]["y"] = drag_data["node"].get("y", 0) + dy
        # 해당 노드와 연결된 화살표 업데이트
        update_arrows(drag_data["node"])

def on_node_release(event):
    if drag_data["node"] is None:
        return

    if drag_data["dragging"]:
        # 마우스 해제 위치에서 겹치는 캔버스 아이템 찾기
        overlapping_items = vis_canvas.find_overlapping(event.x, event.y, event.x, event.y)
        target_node = None
        for item in overlapping_items:
            if item in canvas_node_map:
                candidate = canvas_node_map[item]
                # 자기 자신이나 자손은 제외하여 순환참조 방지
                if candidate is not drag_data["node"] and not is_descendant(drag_data["node"], candidate):
                    target_node = candidate
                    break

        if target_node:
            push_undo()
            # 기존 부모에서 제거
            original_parent = get_parent(tree_data, drag_data["node"])
            if original_parent:
                try:
                    original_parent["children"].remove(drag_data["node"])
                except ValueError:
                    pass
            # 대상 노드의 자식으로 추가
            target_node.setdefault("children", []).append(drag_data["node"])
            save_tree(tree_data)
            refresh_treeview()
            refresh_canvas()
        else:
            # 드롭 대상이 없으면 단순히 위치를 저장
            save_tree(tree_data)
    else:
        # 단순 클릭: 자식 노드 추가 대화상자 실행
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
    """candidate가 parent의 자손(포함)인지 재귀적으로 확인"""
    if parent is candidate:
        return True
    for child in parent.get("children", []):
        if is_descendant(child, candidate):
            return True
    return False

# =======================
# 화살표 연결 관련 함수
# =======================
def get_connection_point(bbox, target_center):
    """
    bbox: (x1, y1, x2, y2) – 노드의 바운딩 박스
    target_center: (x, y) – 연결할 대상 노드의 중심 좌표
    리턴: bbox 경계와 중심을 잇는 선의 교차점 좌표
    """
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
    """
    부모와 자식 노드 사이의 화살표를, 노드의 현재 바운딩 박스 기반으로 업데이트
    """
    parent = get_parent(tree_data, node)
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
                vis_canvas.coords(line_id, start_point[0], start_point[1],
                                  end_point[0], end_point[1])
    # 재귀적으로 자식 노드들에 대해서도 업데이트
    for child in node.get("children", []):
        update_arrows(child)

# =======================
# Canvas에 트리 그리기 – 노드와 화살표 생성
# =======================
def draw_tree(canvas, node, x, y):
    # 노드에 좌표가 있으면 사용, 없으면 초기 좌표 할당
    if "x" in node and "y" in node:
        current_x, current_y = node["x"], node["y"]
    else:
        current_x, current_y = x, y
        node["x"] = x
        node["y"] = y

    # 1. 노드 텍스트 그리기 (중심 정렬, 고유 태그 부여)
    node_tag = f"node_{id(node)}"
    node_text_id = canvas.create_text(current_x, current_y, text=node["name"],
                                      font=("Arial", 12, "bold"),
                                      fill="black", anchor="center",
                                      tags=("node_group", node_tag))
    canvas.update_idletasks()
    bbox = canvas.bbox(node_text_id)
    pad_x, pad_y = 4, 2
    # 2. 텍스트보다 약간 크게 사각형(박스) 그리기 (동일 태그 부여)
    rect_id = canvas.create_rectangle(bbox[0]-pad_x, bbox[1]-pad_y, bbox[2]+pad_x, bbox[3]+pad_y,
                                      fill="white", outline="black",
                                      tags=("node_group", node_tag))
    # 3. 텍스트를 사각형 위로 올림
    canvas.tag_raise(node_text_id, rect_id)
    
    # 4. 텍스트와 사각형을 노드와 연결 (매핑)
    canvas_node_map[node_text_id] = node
    canvas_node_map[rect_id] = node

    # 5. + 버튼 그리기 (노드 옆)
    plus_margin = 8
    plus_x = bbox[2] + plus_margin
    plus_y = (bbox[1] + bbox[3]) / 2 - plus_margin
    plus_tag = f"plus_{id(node)}"
    plus_id = canvas.create_text(plus_x, plus_y, text="+",
                                 font=("Arial", 10, "bold"),
                                 fill="black", tags=("plus", plus_tag))
    canvas_plus_map[plus_id] = node
    canvas.tag_bind(plus_id, "<Button-1>", on_plus_click)

    # 6. 자식 노드들을 재귀적으로 배치 및 부모-자식 연결 화살표 생성
    children = node.get("children", [])
    if children:
        base_width = 80  # 자식들 간 간격
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
                # 초기 화살표는 단순 연결 (update_arrows 함수에서 재계산됨)
                parent_center = ((parent_bbox[0]+parent_bbox[2]) / 2, parent_bbox[3])
                child_top = ((child_bbox[0]+child_bbox[2]) / 2, child_bbox[1])
                line_id = canvas.create_line(parent_center[0], parent_center[1],
                                             child_top[0], child_top[1],
                                             fill="gray", arrow=tk.LAST,
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
    # 루트 노드 좌표가 있으면 사용, 없으면 중앙에 배치
    root_x = tree_data.get("x", width//2)
    root_y = tree_data.get("y", 50)
    draw_tree(vis_canvas, tree_data, root_x, root_y)
    bind_node_group_events(vis_canvas)

# =======================
# 우측 Treeview 및 메모 편집 영역
# =======================
treeview_node_map = {}

def populate_treeview(tv, parent, node):
    item_id = tv.insert(parent, "end", text=node["name"], open=True)
    treeview_node_map[item_id] = node
    for child in node.get("children", []):
        populate_treeview(tv, item_id, child)

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
        push_undo()
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
    push_undo()
    parent_node = treeview_node_map.get(selected[0])
    new_name = simpledialog.askstring("노드 추가", "새로운 노드 이름:")
    if new_name:
        parent_node.setdefault("children", []).append({"name": new_name, "memo": "", "children": []})
        save_tree(tree_data)
        refresh_treeview()
        refresh_canvas()

# =======================
# 초기화 기능
# =======================
def reset_tree():
    if messagebox.askyesno("초기화", "정말 초기화 하시겠습니까?\n기존 데이터는 모두 삭제됩니다."):
        global tree_data
        push_undo()
        tree_data = {"name": "루트", "memo": "", "children": []}
        save_tree(tree_data)
        refresh_treeview()
        refresh_canvas()
        memo_text.delete("1.0", tk.END)
        messagebox.showinfo("초기화", "트리가 초기화되었습니다.")

# =======================
# 메인 윈도우 및 레이아웃 구성
# =======================
root = tk.Tk()
root.title("트리 편집기 (드래그 앤 드롭 및 화살표 업데이트)")
root.geometry("1200x700")

# 좌측 프레임: Canvas 시각화 및 상단 버튼들
left_frame = tk.Frame(root, bg="white")
left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

btn_frame_left = tk.Frame(left_frame, bg="white")
btn_frame_left.pack(side=tk.TOP, fill=tk.X)
reset_btn = tk.Button(btn_frame_left, text="초기화", command=reset_tree)
reset_btn.pack(side=tk.LEFT, padx=5, pady=5)
undo_btn = tk.Button(btn_frame_left, text="Undo", command=undo)
undo_btn.pack(side=tk.LEFT, padx=5, pady=5)
redo_btn = tk.Button(btn_frame_left, text="Redo", command=redo)
redo_btn.pack(side=tk.LEFT, padx=5, pady=5)

vis_canvas = tk.Canvas(left_frame, bg="white")
vis_canvas.pack(fill=tk.BOTH, expand=True)
vis_canvas.bind("<Configure>", lambda event: refresh_canvas())

# 우측 프레임: Treeview 및 메모 편집 영역
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

root.mainloop()
