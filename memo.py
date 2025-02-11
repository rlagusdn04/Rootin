import tkinter as tk  
from tkinter import ttk, simpledialog, messagebox
import json, os, math, copy

# ============================
# TreeModel: 데이터, Undo/Redo 및 ID/추가 부모 연결(extra edge) 관리
# ============================
class TreeModel:
    def __init__(self, json_file="tree_data.json"):
        self.json_file = json_file
        self.next_id = 1  # 노드에 부여할 다음 고유 id
        data = self.load_raw_data()
        # data가 dict이면 (새 포맷: {"tree_data": ..., "extra_edges": ...})
        if isinstance(data, dict) and "tree_data" in data:
            self.tree_data = data.get("tree_data", [])
            self.extra_edges = data.get("extra_edges", [])
        else:
            self.tree_data = data if isinstance(data, list) else [{"name": "루트", "memo": "", "children": []}]
            self.extra_edges = []
        # 모든 노드에 고유 id가 부여되어 있는지 확인
        self.ensure_ids(self.tree_data)
        self.undo_stack = []
        self.redo_stack = []

    def load_raw_data(self):
        if os.path.exists(self.json_file):
            try:
                with open(self.json_file, "r", encoding="utf-8") as file:
                    return json.load(file)
            except json.JSONDecodeError:
                messagebox.showerror("오류", "JSON 파일 형식 오류")
                return [{"name": "루트", "memo": "", "children": []}]
        else:
            return [{"name": "루트", "memo": "", "children": []}]

    def ensure_ids(self, nodes):
        # 재귀적으로 모든 노드에 id를 부여 (이미 있으면 업데이트, 없으면 새로 부여)
        for node in nodes:
            if "id" not in node:
                node["id"] = str(self.next_id)
                self.next_id += 1
            else:
                try:
                    num = int(node["id"])
                    if num >= self.next_id:
                        self.next_id = num + 1
                except:
                    pass
            # memo 필드가 없으면 추가
            if "memo" not in node:
                node["memo"] = ""
            # 자식이 있으면 재귀 호출
            if "children" in node:
                self.ensure_ids(node["children"])
            else:
                node["children"] = []

    def save_tree(self):
        # 저장할 때는 새 포맷 {"tree_data": ..., "extra_edges": ...}로 저장
        with open(self.json_file, "w", encoding="utf-8") as file:
            data = {
                "tree_data": self.tree_data,
                "extra_edges": self.extra_edges
            }
            json.dump(data, file, indent=4, ensure_ascii=False)

    def push_undo(self):
        self.undo_stack.append(copy.deepcopy({"tree_data": self.tree_data, "extra_edges": self.extra_edges}))
        self.redo_stack.clear()

    def undo(self):
        if self.undo_stack:
            self.redo_stack.append(copy.deepcopy({"tree_data": self.tree_data, "extra_edges": self.extra_edges}))
            state = self.undo_stack.pop()
            self.tree_data = state["tree_data"]
            self.extra_edges = state["extra_edges"]
            return True
        else:
            messagebox.showinfo("Undo", "더 이상 실행 취소할 내용이 없습니다.")
            return False

    def redo(self):
        if self.redo_stack:
            self.undo_stack.append(copy.deepcopy({"tree_data": self.tree_data, "extra_edges": self.extra_edges}))
            state = self.redo_stack.pop()
            self.tree_data = state["tree_data"]
            self.extra_edges = state["extra_edges"]
            return True
        else:
            messagebox.showinfo("Redo", "더 이상 재실행할 내용이 없습니다.")
            return False

    def get_node_by_id(self, target_id, nodes=None):
        # 주어진 id를 가진 노드를 재귀적으로 찾음
        if nodes is None:
            nodes = self.tree_data
        for node in nodes:
            if node.get("id") == target_id:
                return node
            result = self.get_node_by_id(target_id, node.get("children", []))
            if result:
                return result
        return None

    def get_parent_recursive(self, node, target):
        # 기존 방식: tree_data를 순회하며 target의 첫번째 부모를 찾음
        for child in node.get("children", []):
            if child is target:
                return node
            p = self.get_parent_recursive(child, target)
            if p:
                return p
        return None

    def get_parent_in_forest(self, forest, target):
        for node in forest:
            if node is target:
                return None
            p = self.get_parent_recursive(node, target)
            if p:
                return p
        return None

    def get_parent(self, target):
        return self.get_parent_in_forest(self.tree_data, target)

    def count_leaves(self, node):
        if not node.get("children"):
            return 1
        return sum(self.count_leaves(child) for child in node["children"])

# ============================
# TreeCanvas: 캔버스 및 노드 그리기/이벤트 처리, 패닝/줌 기능, 추가 부모 연결 지원
# ============================
class TreeCanvas(tk.Canvas):
    def __init__(self, master, model, trash_zone, **kwargs):
        super().__init__(master, **kwargs)
        self.model = model
        self.trash_zone = trash_zone
        self.current_scale = 1.0
        self.canvas_node_map = {}   # {캔버스 항목 id: 노드 id}
        self.canvas_plus_map = {}   # {플러스 항목 id: 노드 id}
        self.arrow_map = {}         # {(부모 id, 자식 id): 선 id} - 기존 부모-자식 관계 선
        self.extra_arrow_map = {}   # {(부모 id, 자식 id): 선 id} - 추가 부모 연결 선
        self.drag_data = {"node": None, "start_x": 0, "start_y": 0, "dragging": False}
        self._panning = False  # 패닝 여부 플래그
        self.pending_additional_parent_child = None  # 추가 부모 연결 모드: 연결할 자식 노드

        self.bind_events()
        self.bind("<MouseWheel>", self.zoom)
        self.bind("<Button-4>", self.zoom)
        self.bind("<Button-5>", self.zoom)
        # 빈 공간에서의 패닝 처리 (Shift 없이)
        self.bind("<ButtonPress-1>", self.on_canvas_press, add="+")
        self.bind("<B1-Motion>", self.on_canvas_drag, add="+")
        self.bind("<ButtonRelease-1>", self.on_canvas_release, add="+")
    
    def bind_events(self):
        self.tag_bind("node_group", "<ButtonPress-1>", self.on_node_press)
        self.tag_bind("node_group", "<B1-Motion>", self.on_node_motion)
        self.tag_bind("node_group", "<ButtonRelease-1>", self.on_node_release)
        self.tag_bind("node_group", "<Button-3>", self.on_node_right_click)
    
    def zoom(self, event):
        if hasattr(event, 'delta'):
            scale_factor = 1.1 if event.delta > 0 else 0.9
        elif event.num == 4:
            scale_factor = 1.1
        elif event.num == 5:
            scale_factor = 0.9
        else:
            return
        x = self.canvasx(event.x)
        y = self.canvasy(event.y)
        self.scale("node_group", x, y, scale_factor, scale_factor)
        self.scale("plus", x, y, scale_factor, scale_factor)
        self.scale("arrow_line", x, y, scale_factor, scale_factor)
        self.scale("extra_arrow", x, y, scale_factor, scale_factor)
        self.current_scale *= scale_factor
        self.update_fonts()
    
    def update_fonts(self):
        for item in self.find_withtag("node_group"):
            if self.type(item) == "text":
                new_font = ("Arial", max(1, int(12 * self.current_scale)), "bold")
                self.itemconfig(item, font=new_font)
        for item in self.find_withtag("plus"):
            new_font = ("Arial", max(1, int(10 * self.current_scale)), "bold")
            self.itemconfig(item, font=new_font)
    
    def refresh(self):
        self.delete("all")
        self.canvas_node_map.clear()
        self.canvas_plus_map.clear()
        self.arrow_map.clear()
        self.extra_arrow_map.clear()
        # 최상위 노드들을 좌측에서 일정 간격으로 배치
        start_x = 100
        start_y = 50
        gap = 150
        for node in self.model.tree_data:
            self.draw_tree(node, start_x, start_y)
            start_x += gap
        self.bind_events()
        self.update_fonts()
        # 추가 부모 연결 선 그리기 (스타일을 기존 선과 동일하게 회색 실선으로 그림)
        for edge in self.model.extra_edges:
            parent_id, child_id = edge
            parent_node = self.model.get_node_by_id(parent_id)
            child_node = self.model.get_node_by_id(child_id)
            if parent_node and child_node:
                parent_bbox = self.bbox(f"node_{parent_id}")
                child_bbox = self.bbox(f"node_{child_id}")
                if parent_bbox and child_bbox:
                    parent_center = ((parent_bbox[0]+parent_bbox[2]) / 2, (parent_bbox[1]+parent_bbox[3]) / 2)
                    child_center = ((child_bbox[0]+child_bbox[2]) / 2, (child_bbox[1]+child_bbox[3]) / 2)
                    line_id = self.create_line(parent_center[0], parent_center[1], child_center[0], child_center[1],
                                                 fill="gray", arrow=tk.LAST,
                                                 tags=("extra_arrow", f"extra_arrow_{parent_id}_{child_id}"))
                    self.extra_arrow_map[(parent_id, child_id)] = line_id

    def draw_tree(self, node, x, y):
        # 노드의 저장된 좌표가 있으면 사용, 없으면 기본값 사용
        if "x" in node and "y" in node:
            current_x, current_y = node["x"], node["y"]
        else:
            current_x, current_y = x, y
            node["x"] = x
            node["y"] = y
        node_tag = f"node_{node['id']}"
        base_font = ("Arial", max(1, int(12 * self.current_scale)), "bold")
        node_text_id = self.create_text(current_x, current_y, text=node["name"],
                                      font=base_font,
                                      fill="black", anchor="center",
                                      tags=("node_group", node_tag))
        self.update_idletasks()
        bbox = self.bbox(node_text_id)
        pad_x, pad_y = 4, 2
        rect_id = self.create_rectangle(bbox[0]-pad_x, bbox[1]-pad_y, bbox[2]+pad_x, bbox[3]+pad_y,
                                      fill="white", outline="black",
                                      tags=("node_group", node_tag))
        self.tag_raise(node_text_id, rect_id)
        self.canvas_node_map[node_text_id] = node["id"]
        self.canvas_node_map[rect_id] = node["id"]
        
        # 플러스 아이콘 (메모 편집/자식 추가)
        plus_margin = 8
        plus_x = bbox[2] + plus_margin
        plus_y = (bbox[1] + bbox[3]) / 2 - plus_margin
        plus_tag = f"plus_{node['id']}"
        plus_font = ("Arial", max(1, int(10 * self.current_scale)), "bold")
        plus_id = self.create_text(plus_x, plus_y, text="+",
                                 font=plus_font,
                                 fill="black", tags=("plus", plus_tag))
        self.canvas_plus_map[plus_id] = node["id"]
        self.tag_bind(plus_id, "<Button-1>", self.on_plus_click)
        
        # 자식 노드 그리기
        children = node.get("children", [])
        if children:
            base_width = 80
            start_x_child = current_x - (len(children)-1) * base_width/2
            child_y = current_y + 80
            for child in children:
                if "x" not in child or "y" not in child:
                    child["x"] = start_x_child
                    child["y"] = child_y
                self.draw_tree(child, child["x"], child_y)
                parent_bbox = self.bbox(node_tag)
                child_bbox = self.bbox(f"node_{child['id']}")
                if parent_bbox and child_bbox:
                    parent_center = ((parent_bbox[0] + parent_bbox[2]) / 2, parent_bbox[3])
                    child_top = ((child_bbox[0] + child_bbox[2]) / 2, child_bbox[1])
                    points = [parent_center[0], parent_center[1], child_top[0], child_top[1]]
                    line_id = self.create_line(*points, fill="gray", arrow=tk.LAST,
                                             tags=("arrow_line", f"arrow_{node['id']}_{child['id']}"))
                    self.arrow_map[(node["id"], child["id"])] = line_id
                start_x_child += base_width

    def on_plus_click(self, event):
        current = self.find_withtag("current")
        if not current:
            return
        item = current[0]
        # canvas_plus_map에 저장된 node id
        node_id = self.canvas_plus_map.get(item)
        if node_id:
            node = self.model.get_node_by_id(node_id)
            if node:
                self.open_memo_popup(node)
    
    def open_memo_popup(self, node):
        popup = tk.Toplevel(self)
        popup.title(f"메모 편집 - {node['name']}")
        text = tk.Text(popup, width=40, height=10)
        text.pack(padx=10, pady=10)
        text.insert(tk.END, node.get("memo", ""))
        def save_and_close():
            self.model.push_undo()
            node["memo"] = text.get("1.0", tk.END).strip()
            self.model.save_tree()
            popup.destroy()
        btn = tk.Button(popup, text="저장", command=save_and_close)
        btn.pack(pady=5)
    
    # -------------------------
    # 노드 드래그 이벤트 (노드 위에서 발생)
    # -------------------------
    def on_node_press(self, event):
        # 만약 추가 부모 연결 모드가 활성화되어 있다면,
        if self.pending_additional_parent_child is not None:
            x = self.canvasx(event.x)
            y = self.canvasy(event.y)
            item = self.find_closest(x, y)
            if item:
                item = item[0]
                if item in self.canvas_node_map:
                    parent_id = self.canvas_node_map[item]
                    child = self.pending_additional_parent_child
                    # 같은 노드를 연결하지 않도록
                    if parent_id == child["id"]:
                        messagebox.showwarning("경고", "부모와 자식이 동일할 수 없습니다.")
                    else:
                        # 이미 해당 추가 연결이 존재하지 않으면 추가
                        exists = False
                        for edge in self.model.extra_edges:
                            if edge[0] == parent_id and edge[1] == child["id"]:
                                exists = True
                                break
                        if not exists:
                            self.model.push_undo()
                            self.model.extra_edges.append([parent_id, child["id"]])
                            self.model.save_tree()
                        else:
                            messagebox.showinfo("정보", "이미 연결되어 있습니다.")
                    self.pending_additional_parent_child = None
                    self.refresh()
                    return "break"
        # 일반적인 노드 선택 및 드래그 시작
        current = self.find_withtag("current")
        if not current:
            return
        item = current[0]
        if item not in self.canvas_node_map:
            return
        node_id = self.canvas_node_map[item]
        node = self.model.get_node_by_id(node_id)
        if not node:
            return
        self.drag_data["node"] = node
        self.drag_data["start_x"] = self.canvasx(event.x)
        self.drag_data["start_y"] = self.canvasy(event.y)
        self.drag_data["dragging"] = False
        self._panning = False
        return "break"
    
    def on_node_motion(self, event):
        if self.drag_data["node"] is None:
            return
        current_x = self.canvasx(event.x)
        current_y = self.canvasy(event.y)
        dx = current_x - self.drag_data["start_x"]
        dy = current_y - self.drag_data["start_y"]
        if math.sqrt(dx*dx + dy*dy) > 5:
            self.drag_data["dragging"] = True
            node_tag = f"node_{self.drag_data['node']['id']}"
            self.move(node_tag, dx, dy)
            plus_tag = f"plus_{self.drag_data['node']['id']}"
            self.move(plus_tag, dx, dy)
            self.drag_data["start_x"] = current_x
            self.drag_data["start_y"] = current_y
            self.drag_data["node"]["x"] = self.drag_data["node"].get("x", 0) + dx
            self.drag_data["node"]["y"] = self.drag_data["node"].get("y", 0) + dy
            self.update_arrows(self.drag_data["node"])
            self.update_extra_arrows()  # 추가 부모 연결 선 업데이트
            if self.trash_zone.is_near(event.x_root, event.y_root):
                self.trash_zone.show_feedback()
            else:
                self.trash_zone.reset_feedback()
        return "break"
    
    def on_node_release(self, event):
        if self.drag_data["node"] is None:
            return "break"
        if self.drag_data["dragging"] and self.trash_zone.is_over(event.x_root, event.y_root):
            self.model.push_undo()
            parent = self.model.get_parent(self.drag_data["node"])
            if parent is not None:
                try:
                    parent["children"].remove(self.drag_data["node"])
                except ValueError:
                    pass
            else:
                try:
                    self.model.tree_data.remove(self.drag_data["node"])
                except ValueError:
                    pass
            self.model.save_tree()
            self.trash_zone.reset_feedback()
            self.refresh()
        elif self.drag_data["dragging"]:
            release_x = self.canvasx(event.x)
            release_y = self.canvasy(event.y)
            overlapping_items = self.find_overlapping(release_x, release_y, release_x, release_y)
            target_node = None
            for item in overlapping_items:
                if item in self.canvas_node_map:
                    candidate = self.model.get_node_by_id(self.canvas_node_map[item])
                    if candidate is not self.drag_data["node"] and not self.is_descendant(self.drag_data["node"], candidate):
                        target_node = candidate
                        break
            if target_node:
                self.model.push_undo()
                original_parent = self.model.get_parent(self.drag_data["node"])
                if original_parent is not None:
                    try:
                        original_parent["children"].remove(self.drag_data["node"])
                    except ValueError:
                        pass
                target_node.setdefault("children", []).append(self.drag_data["node"])
                self.model.save_tree()
                self.refresh()
            else:
                self.model.save_tree()
        else:
            new_name = simpledialog.askstring("노드 추가", f"'{self.drag_data['node']['name']}' 노드에 추가할 자식 노드 이름:")
            if new_name:
                self.model.push_undo()
                self.drag_data["node"].setdefault("children", []).append({"name": new_name, "memo": "", "children": []})
                self.model.save_tree()
                self.refresh()
        self.drag_data["node"] = None
        self.drag_data["dragging"] = False
        self.trash_zone.reset_feedback()
        return "break"
    
    def on_node_right_click(self, event):
        current = self.find_withtag("current")
        if not current:
            return
        item = current[0]
        if item not in self.canvas_node_map:
            return
        node = self.model.get_node_by_id(self.canvas_node_map[item])
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="메모 편집", command=lambda: self.open_memo_popup(node))
        menu.add_command(label="노드 수정", command=lambda: self.rename_node(node))
        menu.add_command(label="노드 삭제", command=lambda: self.delete_node(node))
        menu.add_command(label="자식 추가", command=lambda: self.add_child_node(node))
        menu.add_command(label="추가 부모 연결", command=lambda: self.start_additional_parent(node))
        menu.add_command(label="추가 부모 삭제", command=lambda: self.delete_extra_parent(node))
        menu.post(event.x_root, event.y_root)
        return "break"
    
    def start_additional_parent(self, child_node):
        # child_node에 추가 부모 연결을 추가하기 위해, 다음 클릭할 노드를 부모로 사용하도록 설정
        self.pending_additional_parent_child = child_node
        messagebox.showinfo("알림", "부모 노드를 선택하세요.")
    
    def delete_extra_parent(self, child_node):
        # child_node를 자식으로 갖는 추가 부모 연결 삭제 기능
        child_id = child_node["id"]
        extra_parents = [edge[0] for edge in self.model.extra_edges if edge[1] == child_id]
        if not extra_parents:
            messagebox.showinfo("정보", "삭제할 추가 부모 연결이 없습니다.")
            return
        if len(extra_parents) == 1:
            parent_id = extra_parents[0]
            parent_node = self.model.get_node_by_id(parent_id)
            if messagebox.askyesno("삭제 확인", f"{child_node['name']} 노드의 추가 부모인 {parent_node['name']}와의 연결을 삭제하시겠습니까?"):
                self.model.push_undo()
                self.model.extra_edges = [edge for edge in self.model.extra_edges if not (edge[0] == parent_id and edge[1] == child_id)]
                self.model.save_tree()
                self.refresh()
            return
        # 여러 개라면 팝업창을 띄워 선택하게 함
        popup = tk.Toplevel(self)
        popup.title("추가 부모 연결 삭제")
        label = tk.Label(popup, text="삭제할 추가 부모 연결을 선택하세요:")
        label.pack(padx=10, pady=10)
        listbox = tk.Listbox(popup)
        parent_map = {}
        for i, parent_id in enumerate(extra_parents):
            parent_node = self.model.get_node_by_id(parent_id)
            display_name = parent_node["name"] if parent_node else f"부모 ID: {parent_id}"
            listbox.insert(tk.END, display_name)
            parent_map[i] = parent_id
        listbox.pack(padx=10, pady=10)
        def delete_selected():
            selection = listbox.curselection()
            if not selection:
                messagebox.showwarning("선택", "삭제할 연결을 선택하세요.")
                return
            index = selection[0]
            parent_id = parent_map[index]
            parent_node = self.model.get_node_by_id(parent_id)
            if messagebox.askyesno("삭제 확인", f"{child_node['name']} 노드의 추가 부모인 {parent_node['name']}와의 연결을 삭제하시겠습니까?"):
                self.model.push_undo()
                self.model.extra_edges = [edge for edge in self.model.extra_edges if not (edge[0] == parent_id and edge[1] == child_id)]
                self.model.save_tree()
                self.refresh()
                popup.destroy()
        delete_btn = tk.Button(popup, text="삭제", command=delete_selected)
        delete_btn.pack(padx=10, pady=10)
    
    def rename_node(self, node):
        new_name = simpledialog.askstring("노드 수정", "새로운 이름을 입력하세요:", initialvalue=node["name"])
        if new_name:
            self.model.push_undo()
            node["name"] = new_name
            self.model.save_tree()
            self.refresh()
    
    def delete_node(self, node):
        self.model.push_undo()
        parent = self.model.get_parent(node)
        if parent is not None:
            try:
                parent["children"].remove(node)
            except ValueError:
                pass
        else:
            try:
                self.model.tree_data.remove(node)
            except ValueError:
                pass
        # 삭제된 노드와 관련된 추가 부모 연결도 제거
        self.model.extra_edges = [edge for edge in self.model.extra_edges if edge[0] != node["id"] and edge[1] != node["id"]]
        self.model.save_tree()
        self.refresh()
    
    def add_child_node(self, node):
        new_name = simpledialog.askstring("노드 추가", f"'{node['name']}' 노드에 추가할 자식 노드 이름:")
        if new_name:
            self.model.push_undo()
            node.setdefault("children", []).append({"name": new_name, "memo": "", "children": []})
            self.model.save_tree()
            self.refresh()
    
    def update_arrows(self, node):
        parent = self.model.get_parent(node)
        if parent:
            key = (parent["id"], node["id"])
            if key in self.arrow_map:
                line_id = self.arrow_map[key]
                parent_bbox = self.bbox(f"node_{parent['id']}")
                child_bbox = self.bbox(f"node_{node['id']}")
                if parent_bbox and child_bbox:
                    parent_center = ((parent_bbox[0] + parent_bbox[2]) / 2,
                                     (parent_bbox[1] + parent_bbox[3]) / 2)
                    child_center = ((child_bbox[0] + child_bbox[2]) / 2,
                                    (child_bbox[1] + child_bbox[3]) / 2)
                    start_point = self.get_connection_point(parent_bbox, child_center)
                    end_point = self.get_connection_point(child_bbox, parent_center)
                    points = [start_point[0], start_point[1], end_point[0], end_point[1]]
                    self.coords(line_id, *points)
        for child in node.get("children", []):
            self.update_arrows(child)

    def update_extra_arrows(self):
        # model.extra_edges에 저장된 모든 추가 부모 연결(스타일 동일한 회색 실선)을 업데이트
        for edge in self.model.extra_edges:
            parent_id, child_id = edge
            if (parent_id, child_id) in self.extra_arrow_map:
                line_id = self.extra_arrow_map[(parent_id, child_id)]
                parent_bbox = self.bbox(f"node_{parent_id}")
                child_bbox = self.bbox(f"node_{child_id}")
                if parent_bbox and child_bbox:
                    parent_center = ((parent_bbox[0] + parent_bbox[2]) / 2,
                                     (parent_bbox[1] + parent_bbox[3]) / 2)
                    child_center = ((child_bbox[0] + child_bbox[2]) / 2,
                                    (child_bbox[1] + child_bbox[3]) / 2)
                    self.coords(line_id, parent_center[0], parent_center[1],
                                child_center[0], child_center[1])
    
    def get_connection_point(self, bbox, target_center):
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
    
    def is_descendant(self, parent, candidate):
        if parent is candidate:
            return True
        for child in parent.get("children", []):
            if self.is_descendant(child, candidate):
                return True
        return False

    # -------------------------
    # 캔버스 빈 공간에서의 패닝 처리 (노드가 없으면 패닝)
    # -------------------------
    def on_canvas_press(self, event):
        # 우선 pending_additional_parent_child가 활성화되어 있으면 이를 처리
        if self.pending_additional_parent_child is not None:
            x = self.canvasx(event.x)
            y = self.canvasy(event.y)
            item = self.find_closest(x, y)
            if item:
                item = item[0]
                if item in self.canvas_node_map:
                    parent_id = self.canvas_node_map[item]
                    child = self.pending_additional_parent_child
                    if parent_id == child["id"]:
                        messagebox.showwarning("경고", "부모와 자식이 동일할 수 없습니다.")
                    else:
                        exists = False
                        for edge in self.model.extra_edges:
                            if edge[0] == parent_id and edge[1] == child["id"]:
                                exists = True
                                break
                        if not exists:
                            self.model.push_undo()
                            self.model.extra_edges.append([parent_id, child["id"]])
                            self.model.save_tree()
                        else:
                            messagebox.showinfo("정보", "이미 연결되어 있습니다.")
                    self.pending_additional_parent_child = None
                    self.refresh()
                    return "break"
        # 일반 패닝 처리: 만약 "current" 항목이 있다면 노드/플러스 클릭이므로 패닝 취소
        current = self.find_withtag("current")
        if current:
            tags = self.gettags(current[0])
            if "node_group" in tags or "plus" in tags:
                self._panning = False
                return "break"
        self._panning = True
        self.scan_mark(event.x, event.y)
        return "break"
    
    def on_canvas_drag(self, event):
        if self._panning:
            self.scan_dragto(event.x, event.y, gain=1)
            return "break"
    
    def on_canvas_release(self, event):
        self._panning = False
        return "break"

# ============================
# TrashZone: 삭제 영역 (노드 드래그 시 피드백 제공)
# ============================
class TrashZone:
    def __init__(self, master, x, y, default_size=(50, 50), expanded_size=(100, 100)):
        self.master = master
        self.x, self.y = x, y
        self.default_size = default_size
        self.expanded_size = expanded_size
        self.frame = tk.Frame(master, width=default_size[0], height=default_size[1],
                              bg="red", bd=2, relief="raised")
        self.show()
    
    def show(self):
        self.frame.place(x=self.x, y=self.y)
    
    def hide(self):
        self.frame.place_forget()
    
    def show_feedback(self):
        self.frame.config(width=self.expanded_size[0], height=self.expanded_size[1],
                          bg="#FF0000", bd=2, relief="raised")
        self.frame.place(x=self.x, y=self.y)
    
    def reset_feedback(self):
        self.frame.config(width=self.default_size[0], height=self.default_size[1],
                          bg="red", bd=2, relief="raised")
        self.frame.place(x=self.x, y=self.y)
    
    def is_over(self, x_root, y_root):
        trash_x = self.frame.winfo_rootx()
        trash_y = self.frame.winfo_rooty()
        trash_width = self.frame.winfo_width()
        trash_height = self.frame.winfo_height()
        return (trash_x <= x_root <= trash_x + trash_width and 
                trash_y <= y_root <= trash_y + trash_height)
    
    def is_near(self, x_root, y_root, threshold=100):
        trash_cx = self.frame.winfo_rootx() + self.frame.winfo_width() // 2
        trash_cy = self.frame.winfo_rooty() + self.frame.winfo_height() // 2
        dx = x_root - trash_cx
        dy = y_root - trash_cy
        distance = math.sqrt(dx*dx + dy*dy)
        return distance < threshold

# ============================
# TreeViewPanel: 우측의 트리뷰 및 메모 편집 영역
# ============================
class TreeViewPanel(tk.Frame):
    def __init__(self, master, model, canvas, **kwargs):
        super().__init__(master, **kwargs)
        self.model = model
        self.canvas = canvas
        self.treeview = ttk.Treeview(self)
        self.treeview.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.treeview.bind("<<TreeviewSelect>>", self.on_treeview_select)
        btn_frame = tk.Frame(self)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)
        add_node_btn = tk.Button(btn_frame, text="노드 추가", command=self.add_node)
        add_node_btn.pack(side=tk.LEFT, padx=5)
        save_memo_btn = tk.Button(btn_frame, text="메모 저장", command=self.save_memo)
        save_memo_btn.pack(side=tk.LEFT, padx=5)
        self.memo_text = tk.Text(self, height=10)
        self.memo_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.treeview_node_map = {}
        self.refresh()
    
    def populate_treeview(self, parent, node):
        item_id = self.treeview.insert(parent, "end", text=node["name"], open=True)
        self.treeview_node_map[item_id] = node
        for child in node.get("children", []):
            self.populate_treeview(item_id, child)
    
    def refresh(self):
        self.treeview.delete(*self.treeview.get_children())
        self.treeview_node_map.clear()
        for node in self.model.tree_data:
            self.populate_treeview("", node)
    
    def on_treeview_select(self, event):
        selected = self.treeview.selection()
        if selected:
            node = self.treeview_node_map.get(selected[0])
            self.memo_text.delete("1.0", tk.END)
            self.memo_text.insert(tk.END, node.get("memo", ""))
        else:
            self.memo_text.delete("1.0", tk.END)
    
    def save_memo(self):
        selected = self.treeview.selection()
        if selected:
            self.model.push_undo()
            node = self.treeview_node_map.get(selected[0])
            node["memo"] = self.memo_text.get("1.0", tk.END).strip()
            self.model.save_tree()
            messagebox.showinfo("저장", "메모가 저장되었습니다.")
        else:
            messagebox.showwarning("선택", "노드를 선택하세요.")
    
    def add_node(self):
        self.model.push_undo()
        selected = self.treeview.selection()
        new_name = simpledialog.askstring("노드 추가", "새로운 노드 이름:")
        if not new_name:
            return
        if selected:
            parent_node = self.treeview_node_map.get(selected[0])
            parent_node.setdefault("children", []).append({"name": new_name, "memo": "", "children": []})
        else:
            self.model.tree_data.append({"name": new_name, "memo": "", "children": []})
        self.model.save_tree()
        self.refresh()
        self.canvas.refresh()

    def reset_tree(self):
        if messagebox.askyesno("초기화", "정말 초기화 하시겠습니까?\n기존 데이터는 모두 삭제됩니다."):
            self.model.push_undo()
            self.model.tree_data = [{"name": "루트", "memo": "", "children": []}]
            self.model.extra_edges = []
            self.model.save_tree()
            self.refresh()
            self.canvas.refresh()
            self.memo_text.delete("1.0", tk.END)
            messagebox.showinfo("초기화", "트리가 초기화되었습니다.")

# ============================
# TreeEditorApp: 메인 애플리케이션 클래스
# ============================
class TreeEditorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("트리 편집기 (패닝, 줌, Trash 피드백)")
        self.root.geometry("1200x700")
        
        # 모델 생성
        self.model = TreeModel()
        
        # 왼쪽: 캔버스 영역
        left_frame = tk.Frame(root, bg="white")
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 좌측 상단 버튼: 초기화, Undo, Redo
        btn_frame_left = tk.Frame(left_frame, bg="white")
        btn_frame_left.pack(side=tk.TOP, fill=tk.X)
        reset_btn = tk.Button(btn_frame_left, text="초기화", command=self.reset_tree)
        reset_btn.pack(side=tk.LEFT, padx=5, pady=5)
        undo_btn = tk.Button(btn_frame_left, text="Undo", command=self.undo)
        undo_btn.pack(side=tk.LEFT, padx=5, pady=5)
        redo_btn = tk.Button(btn_frame_left, text="Redo", command=self.redo)
        redo_btn.pack(side=tk.LEFT, padx=5, pady=5)
        
        # TrashZone 생성 (left_frame 내에 위치)
        self.trash_zone = TrashZone(left_frame, x=0, y=0)
        left_frame.bind("<Configure>", self.update_trash_zone_position)
        
        # 캔버스 생성 (스크롤바 없이 패닝/줌 사용)
        self.canvas = TreeCanvas(left_frame, self.model, self.trash_zone, bg="white")
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # 오른쪽: TreeView 및 메모 편집 영역
        right_frame = tk.Frame(root)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH)
        self.treeview_panel = TreeViewPanel(right_frame, self.model, self.canvas)
        self.treeview_panel.pack(fill=tk.BOTH, expand=True)
        
        # 초기 그리기
        self.canvas.refresh()
        self.treeview_panel.refresh()
    
    def update_trash_zone_position(self, event):
        x = event.width - self.trash_zone.default_size[0] - 10
        y = event.height - self.trash_zone.default_size[1] - 10
        self.trash_zone.x = x
        self.trash_zone.y = y
        self.trash_zone.reset_feedback()
    
    def reset_tree(self):
        self.treeview_panel.reset_tree()
    
    def undo(self):
        if self.model.undo():
            self.canvas.refresh()
            self.treeview_panel.refresh()
    
    def redo(self):
        if self.model.redo():
            self.canvas.refresh()
            self.treeview_panel.refresh()

# ============================
# 메인 실행부
# ============================
if __name__ == "__main__":
    root = tk.Tk()
    app = TreeEditorApp(root)
    root.mainloop()
